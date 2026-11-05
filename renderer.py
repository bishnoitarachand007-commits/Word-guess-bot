import os
from PIL import Image, ImageDraw, ImageFont

WIDTH, HEIGHT = 720, 1120

FONT_PATH = os.path.join(os.path.dirname(os.path.abspath(__file__)), "DejaVuSans-Bold.ttf")

COLORS = {
    "correct": (20, 205, 125),
    "present": (155, 75, 235),
    "absent": (225, 45, 65),
    "empty": (27, 34, 65),
}

def get_font(letter):
    for size in range(110, 50, -2):
        font = ImageFont.truetype(FONT_PATH, size)
        box = font.getbbox(letter, stroke_width=1)

        if box[2] - box[0] <= 108 and box[3] - box[1] <= 108:
            return font

    return ImageFont.truetype(FONT_PATH, 50)

def save_board(history=None, filename="board.png"):
    history = history or []

    img = Image.new("RGB", (WIDTH, HEIGHT), (9, 12, 30))
    draw = ImageDraw.Draw(img)

    tile_size = 118
    gap = 14

    left = (WIDTH - (5 * tile_size + 4 * gap)) // 2
    top = (HEIGHT - (8 * tile_size + 7 * gap)) // 2

    visible = history[-8:]

    for row in range(8):
        for col in range(5):
            x = left + col * (tile_size + gap)
            y = top + row * (tile_size + gap)

            letter = ""
            color = COLORS["empty"]

            if row < len(visible):
                guess, feedback = visible[row]
                letter = guess[col]
                color = COLORS[feedback[col]]

            draw.rounded_rectangle(
                (x, y, x + tile_size, y + tile_size),
                radius=12,
                fill=color
            )

            if letter:
                font = get_font(letter)

                draw.text(
                    (x + tile_size // 2, y + tile_size // 2),
                    letter,
                    font=font,
                    fill=(255, 255, 255),
                    anchor="mm",
                    stroke_width=1,
                    stroke_fill=(0, 0, 0)
                )

    img.save(filename)
    return filename
