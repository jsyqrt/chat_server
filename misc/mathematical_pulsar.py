import numpy as np
import matplotlib.pyplot as plt
from matplotlib.path import Path
import matplotlib.patches as patches
import os
import glob
from PIL import Image, ImageDraw

# 定义彩虹七种颜色
RAINBOW_COLORS = [
    # ('black', '#000000'),
    # ('red', '#FF0000'),
    # ('orange', '#FF7F00'),
    # ('yellow', '#FFFF00'),
    # ('green', '#00FF00'),
    # ('cyan', '#00FFFF'),
    ('blue', '#4285f4'),
    # ('purple', '#8F00FF')
]

def save_current_state(ax, step_number, description, bg_color='black'):
    """保存当前绘制状态"""
    plt.savefig(f'step_{step_number:03d}_{description}.png',
                facecolor=bg_color, bbox_inches='tight', dpi=300)

def create_figure(bg_color='black'):
    """创建基本的图形对象"""
    fig = plt.figure(figsize=(10, 10), facecolor=bg_color)
    ax = plt.gca()
    ax.set_facecolor(bg_color)
    ax.set_xlim(-400, 400)
    ax.set_ylim(-400, 400)
    ax.axis('off')
    ax.set_aspect('equal')
    plt.subplots_adjust(left=0, right=1, top=1, bottom=0)
    return ax, fig

def draw_central_sphere(ax, step_counter, bg_color='black'):
    """绘制中心球体"""
    circle = plt.Circle((0, 0), 40, color='white', ec='white', linewidth=2)
    ax.add_patch(circle)
    save_current_state(ax, step_counter[0], "central_sphere", bg_color)
    step_counter[0] += 1

def calculate_ellipse_points(level):
    """计算椭圆的点集
    方程：(5x² + 16xy + 5y²) = level
    """
    theta = np.linspace(0, 2*np.pi, 100000)
    r = np.sqrt(level / (5 + 2*8*np.sin(theta)*np.cos(theta) + 5))
    x = r * np.cos(theta)
    y = r * np.sin(theta)
    return x, y

def draw_half_ring(ax, inner_level, outer_level, is_upper_right, step_counter, ring_number, bg_color='black'):
    """绘制半个环"""
    x_inner, y_inner = calculate_ellipse_points(inner_level)
    x_outer, y_outer = calculate_ellipse_points(outer_level)

    if is_upper_right:
        mask = (y_outer >= -x_outer)
        position = "upper_right"
    else:
        mask = (y_outer <= -x_outer)
        position = "lower_left"

    # 移除闭合点，让matplotlib自动处理闭合
    x = np.concatenate([
        x_outer[mask],
        x_inner[mask][::-1]
    ])
    y = np.concatenate([
        y_outer[mask],
        y_inner[mask][::-1]
    ])

    # 使用edgecolor='none'去掉边界线，避免出现不合适的线条
    ax.fill(x, y, 'white', alpha=1.0 if not is_upper_right else 0.8, edgecolor='none')
    save_current_state(ax, step_counter[0], f"ring_{position}_{ring_number}", bg_color)
    step_counter[0] += 1

def draw_jet_pair(ax, x_range, is_first_pair, step_counter, bg_color='black'):
    """绘制一对喷流"""

    if is_first_pair:
        # For first pair: y = x ± sqrt(32x), valid when x >= 0
        x = np.linspace(0, x_range, 5000)  # Only positive x values
        sqrt_term = np.sqrt(32 * x)  # 16*(x+x) = 32*x
        y1 = x + sqrt_term
        y2 = x - sqrt_term
        pair_name = "first"
    else:
        # For second pair: y = x ± sqrt(-32x), valid when x <= 0
        x = np.linspace(-x_range, 0, 5000)  # Only negative x values
        sqrt_term = np.sqrt(-32 * x)  # sqrt(-32*x) is valid when x <= 0
        y1 = x + sqrt_term
        y2 = x - sqrt_term
        pair_name = "second"

    # Create the filled region
    x_fill = np.concatenate([x, x[::-1]])
    y_fill = np.concatenate([y1, y2[::-1]])

    # Fill the area
    ax.fill(x_fill, y_fill, 'white' , alpha=1 if is_first_pair else 0.8, edgecolor='none')

    save_current_state(ax, step_counter[0], f"jet_{pair_name}", bg_color)
    step_counter[0] += 1

def draw_upper_right_part(ax, ring_pairs, step_counter, bg_color='black'):
    """绘制右上部分（从外到内）"""
    # 从外到内画星环
    for i, (inner_level, outer_level) in enumerate(reversed(ring_pairs)):
        draw_half_ring(ax, inner_level, outer_level, True, step_counter, i, bg_color)

    # 画右上部分的喷流
    draw_jet_pair(ax, 400, True, step_counter, bg_color)

    # 最后画球体
    draw_central_sphere(ax, step_counter, bg_color)

def draw_lower_left_part(ax, ring_pairs, step_counter, bg_color='black'):
    """绘制左下部分（从内到外）"""
    # 先画喷流
    draw_jet_pair(ax, 400, False, step_counter, bg_color)

    # 画球体
    draw_central_sphere(ax, step_counter, bg_color)

    # 从内到外画星环
    for i, (inner_level, outer_level) in enumerate(ring_pairs):
        draw_half_ring(ax, inner_level, outer_level, False, step_counter, i, bg_color)

def apply_rounded_corners(image_path, corner_radius=50, suffix=""):
    """将图像应用圆角矩形遮罩 - 通用实现"""
    from PIL import Image, ImageDraw

    # 打开原图像
    img = Image.open(image_path).convert("RGBA")
    width, height = img.size

    # 创建遮罩
    mask = Image.new('L', (width, height), 0)  # 黑色背景（透明）
    draw = ImageDraw.Draw(mask)

    # 绘制中心的十字形区域（白色=不透明）
    # 水平条
    draw.rectangle([corner_radius, 0, width-corner_radius, height], fill=255)
    # 垂直条
    draw.rectangle([0, corner_radius, width, height-corner_radius], fill=255)

    # 绘制四个圆角（使用椭圆的四分之一）
    # 左上角
    draw.ellipse([0, 0, corner_radius*2, corner_radius*2], fill=255)
    # 右上角
    draw.ellipse([width-corner_radius*2, 0, width, corner_radius*2], fill=255)
    # 左下角
    draw.ellipse([0, height-corner_radius*2, corner_radius*2, height], fill=255)
    # 右下角
    draw.ellipse([width-corner_radius*2, height-corner_radius*2, width, height], fill=255)

    # 应用遮罩
    img.putalpha(mask)

    rounded_image_path = image_path.replace('.png', '_rounded.png')

    img.save(rounded_image_path, "PNG")
    print(f"圆角图像已保存: {rounded_image_path}")

    return rounded_image_path

def create_mathematical_pulsar(bg_color='black', color_name='black'):
    """创建数学脉冲星图像"""
    # 清理之前的图片
    for f in glob.glob('step_*.png'):
        os.remove(f)

    # 步骤计数器（使用列表以便在函数间共享）
    step_counter = [0]

    # 创建图形
    ax, fig = create_figure(bg_color)

    # 定义环的参数
    ring_pairs = [
        (20000, 40000),
        (80000, 160000),
        (320000, 600000),
    ]

    # 先画右上部分（从外到内）
    draw_upper_right_part(ax, ring_pairs, step_counter, bg_color)

    # 再画左下部分（从内到外）
    draw_lower_left_part(ax, ring_pairs, step_counter, bg_color)

    # 保存最终图像
    original_image = f'mathematical_pulsar_{color_name}.png'
    plt.savefig(original_image, facecolor=bg_color, dpi=300,
                bbox_inches=None, pad_inches=0)
    plt.close()

    # 创建圆角矩形版本
    print(f"正在创建 {color_name} 背景的圆角矩形版本...")
    rounded_image = apply_rounded_corners(original_image, corner_radius=400)
    print(f"{color_name} 背景的圆角图像已保存为: {rounded_image}")

    return original_image, rounded_image

def main():
    """主函数：生成彩虹七种颜色的脉冲星图像"""
    print("开始生成彩虹七色背景的数学脉冲星图像...")

    for color_name, color_code in RAINBOW_COLORS:
        print(f"\n正在生成 {color_name} ({color_code}) 背景的图像...")
        original, rounded = create_mathematical_pulsar(color_code, color_name)
        print(f"✓ {color_name} 背景图像生成完成")

    print(f"\n🎉 所有 {len(RAINBOW_COLORS)} 种彩虹色背景的图像生成完成！")

if __name__ == "__main__":
    main()