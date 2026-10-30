# -*- coding: utf-8 -*-
"""Blender headless: 加载GLB -> 绿幕背景 -> 360°转身循环视频
用法: blender.exe -b -P render_turntable.py -- <glb路径> <输出mp4> [帧数] [分辨率高]
Eevee渲染, 25fps, 首尾无缝循环(360°整圈)
"""
import bpy
import math
import sys
import os

argv = sys.argv[sys.argv.index("--") + 1:] if "--" in sys.argv else []
glb_path = argv[0] if len(argv) > 0 else r"D:\ai-companion\bride_views\bride_pbr_model.glb"
out_path = argv[1] if len(argv) > 1 else r"D:\ai-companion\bride_views\bride_turntable.mp4"
frames = int(argv[2]) if len(argv) > 2 else 200   # 25fps x 8s
res_h = int(argv[3]) if len(argv) > 3 else 960

# ---------- 清空场景 ----------
bpy.ops.wm.read_factory_settings(use_empty=True)

# ---------- 导入GLB ----------
bpy.ops.import_scene.gltf(filepath=glb_path)
objs = [o for o in bpy.context.scene.objects if o.type == 'MESH']
assert objs, "GLB里没有mesh"

# 合并计算包围盒
import mathutils
mins = mathutils.Vector((1e9, 1e9, 1e9))
maxs = mathutils.Vector((-1e9, -1e9, -1e9))
for o in objs:
    for corner in o.bound_box:
        wc = o.matrix_world @ mathutils.Vector(corner)
        mins.x = min(mins.x, wc.x); mins.y = min(mins.y, wc.y); mins.z = min(mins.z, wc.z)
        maxs.x = max(maxs.x, wc.x); maxs.y = max(maxs.y, wc.y); maxs.z = max(maxs.z, wc.z)
center = (mins + maxs) / 2
height = maxs.z - mins.z
radius = max(maxs.x - mins.x, maxs.y - mins.y) / 2
print(f"MODEL bbox center={center} height={height} radius={radius}")

# ---------- 世界: 纯绿幕背景 (世界着色器) ----------
world = bpy.data.worlds.new("GreenWorld")
bpy.context.scene.world = world
world.use_nodes = True
bg = world.node_tree.nodes["Background"]
bg.inputs[0].default_value = (0.0, 1.0, 0.0, 1.0)   # 纯绿
bg.inputs[1].default_value = 1.0

# ---------- 相机: 固定位置, 模型转身(避免背景透视变化) ----------
cam_dist = radius * 3.2 + height * 0.18
cam_data = bpy.data.cameras.new("Camera")
cam = bpy.data.objects.new("Camera", cam_data)
bpy.context.scene.collection.objects.link(cam)
bpy.context.scene.camera = cam
cam.location = (center.x - cam_dist, center.y, center.z + height * 0.05)
cam_h = center.z + height * 0.05
direction = mathutils.Vector((center.x, center.y, center.z + height * 0.02)) - cam.location
cam.rotation_euler = direction.to_track_quat('-Z', 'Y').to_euler()

# 竖屏9:16, 全身入镜
scene = bpy.context.scene
scene.render.resolution_x = int(res_h * 9 / 16) // 2 * 2
scene.render.resolution_y = res_h
# 直接设垂直视角(Blender 5无sensor_y)
import math as m
required = height * 1.18
fov = 2 * m.atan((required / 2) / cam_dist)
cam_data.sensor_fit = 'VERTICAL'
cam_data.angle_y = fov
print(f"CAM dist={cam_dist:.3f} fov={m.degrees(fov):.1f}deg res={scene.render.resolution_x}x{res_h}")

# ---------- 灯光: 三点布光 ----------
def add_light(name, loc, energy, ltype='AREA'):
    d = bpy.data.lights.new(name, type=ltype)
    d.energy = energy
    o = bpy.data.objects.new(name, d)
    o.location = loc
    bpy.context.scene.collection.objects.link(o)
    return o

add_light("Key", (center.x - cam_dist * 0.6, center.y - cam_dist * 0.8, center.z + height * 0.9), height * 900)
add_light("Fill", (center.x - cam_dist * 0.9, center.y + cam_dist * 0.4, center.z + height * 0.3), height * 350)
add_light("Rim", (center.x + cam_dist * 0.5, center.y + cam_dist * 0.6, center.z + height * 0.8), height * 500)

# ---------- 转身动画: 以模型包围盒中心为轴, Z轴360° ----------
# 建一个空物体作为转轴
pivot = bpy.data.objects.new("Pivot", None)
pivot.location = (center.x, center.y, center.z)
bpy.context.scene.collection.objects.link(pivot)
for o in objs:
    o.parent = pivot
    o.matrix_parent_inverse = pivot.matrix_world.inverted()

scene.frame_start = 1
scene.frame_end = frames
scene.render.fps = 25

# Blender 5 slotted actions: 逐帧设值+插帧(线性), 首尾无缝(最后一帧差一步满360)
scene.frame_set(1)
for i in range(1, frames + 1):
    scene.frame_set(i)
    pivot.rotation_euler = (0.0, 0.0, 2 * math.pi * (i - 1) / frames)
    pivot.keyframe_insert(data_path="rotation_euler", frame=i)
# 逐帧打点已足够平滑, 无需再设插值(Blender 5 slotted action API变更)

# ---------- 渲染设置: Eevee(快) ----------
scene.render.engine = 'BLENDER_EEVEE'  # Blender 4.2+统一叫BLENDER_EEVEE
try:
    eevee = scene.eevee
    eevee.taa_render_samples = 32
except Exception:
    pass
# Blender 5.2: 渲染PNG序列, 之后ffmpeg合成
frames_dir = out_path.rsplit(".", 1)[0] + "_frames"
os.makedirs(frames_dir, exist_ok=True)
scene.render.image_settings.file_format = 'PNG'
scene.render.filepath = os.path.join(frames_dir, "f_")

print("RENDER START", frames_dir)
bpy.ops.render.render(animation=True)
print("RENDER DONE frames at", frames_dir)
