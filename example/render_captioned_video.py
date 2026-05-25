from __future__ import annotations

import argparse
import json
import math
import subprocess
from pathlib import Path

from PIL import Image, ImageDraw, ImageFont


def ffprobe_json(path: Path) -> dict:
    result = subprocess.run(
        [
            "ffprobe",
            "-v",
            "error",
            "-print_format",
            "json",
            "-show_streams",
            "-show_format",
            str(path),
        ],
        check=True,
        capture_output=True,
        text=True,
    )
    return json.loads(result.stdout)


def parse_srt_timestamp(value: str) -> float:
    hhmmss, millis = value.split(",")
    hh, mm, ss = [int(part) for part in hhmmss.split(":")]
    return hh * 3600 + mm * 60 + ss + int(millis) / 1000


def parse_srt(path: Path) -> list[dict]:
    entries: list[dict] = []
    blocks = path.read_text(encoding="utf-8").strip().split("\n\n")
    for block in blocks:
        lines = [line.rstrip() for line in block.splitlines() if line.strip()]
        if len(lines) < 3:
            continue
        timing = lines[1]
        start_raw, end_raw = [part.strip() for part in timing.split("-->")]
        entries.append(
            {
                "start": parse_srt_timestamp(start_raw),
                "end": parse_srt_timestamp(end_raw),
                "text": "\n".join(lines[2:]),
            }
        )
    return entries


def format_font(size: int) -> ImageFont.FreeTypeFont | ImageFont.ImageFont:
    candidates = [
        "/System/Library/Fonts/Supplemental/Arial.ttf",
        "/System/Library/Fonts/Supplemental/Helvetica.ttc",
        "/Library/Fonts/Arial.ttf",
    ]
    for candidate in candidates:
        path = Path(candidate)
        if path.exists():
            try:
                return ImageFont.truetype(str(path), size=size)
            except OSError:
                continue
    return ImageFont.load_default()


def wrap_text(draw: ImageDraw.ImageDraw, text: str, font: ImageFont.ImageFont, max_width: int) -> str:
    wrapped_lines: list[str] = []
    for paragraph in text.split("\n"):
        words = paragraph.split()
        if not words:
            wrapped_lines.append("")
            continue
        current = words[0]
        for word in words[1:]:
            candidate = f"{current} {word}"
            bbox = draw.multiline_textbbox((0, 0), candidate, font=font, spacing=8)
            if bbox[2] - bbox[0] <= max_width:
                current = candidate
            else:
                wrapped_lines.append(current)
                current = word
        wrapped_lines.append(current)
    return "\n".join(wrapped_lines)


def active_caption(captions: list[dict], timestamp: float) -> str | None:
    for entry in captions:
        if entry["start"] <= timestamp < entry["end"]:
            return entry["text"]
    return None


def main() -> None:
    parser = argparse.ArgumentParser()
    parser.add_argument("--input", required=True)
    parser.add_argument("--srt", required=True)
    parser.add_argument("--output", required=True)
    args = parser.parse_args()

    input_path = Path(args.input)
    srt_path = Path(args.srt)
    output_path = Path(args.output)

    probe = ffprobe_json(input_path)
    video_stream = next(stream for stream in probe["streams"] if stream["codec_type"] == "video")
    width = int(video_stream["width"])
    height = int(video_stream["height"])
    fps_num, fps_den = [int(part) for part in video_stream["r_frame_rate"].split("/")]
    fps = fps_num / fps_den
    frame_count = int(video_stream.get("nb_frames") or math.floor(float(probe["format"]["duration"]) * fps))

    captions = parse_srt(srt_path)
    font = format_font(28)
    small_font = format_font(22)

    decode = subprocess.Popen(
        [
            "ffmpeg",
            "-v",
            "error",
            "-i",
            str(input_path),
            "-f",
            "rawvideo",
            "-pix_fmt",
            "rgb24",
            "-",
        ],
        stdout=subprocess.PIPE,
    )
    encode = subprocess.Popen(
        [
            "ffmpeg",
            "-y",
            "-v",
            "error",
            "-f",
            "rawvideo",
            "-pix_fmt",
            "rgb24",
            "-s",
            f"{width}x{height}",
            "-r",
            f"{fps}",
            "-i",
            "-",
            "-an",
            "-c:v",
            "libx264",
            "-preset",
            "veryfast",
            "-crf",
            "20",
            "-pix_fmt",
            "yuv420p",
            str(output_path),
        ],
        stdin=subprocess.PIPE,
    )

    assert decode.stdout is not None
    assert encode.stdin is not None
    frame_size = width * height * 3

    for frame_index in range(frame_count):
        raw = decode.stdout.read(frame_size)
        if len(raw) < frame_size:
            break

        timestamp = frame_index / fps
        image = Image.frombytes("RGB", (width, height), raw)
        caption = active_caption(captions, timestamp)

        if caption:
            draw = ImageDraw.Draw(image, "RGBA")
            wrapped = wrap_text(draw, caption, font, max_width=width - 220)
            bbox = draw.multiline_textbbox((0, 0), wrapped, font=font, spacing=8)
            box_width = bbox[2] - bbox[0] + 80
            box_height = bbox[3] - bbox[1] + 54
            box_x = (width - box_width) // 2
            box_y = height - box_height - 42
            draw.rounded_rectangle(
                (box_x, box_y, box_x + box_width, box_y + box_height),
                radius=26,
                fill=(14, 23, 38, 190),
                outline=(255, 255, 255, 26),
                width=2,
            )
            draw.multiline_text(
                (box_x + 40, box_y + 22),
                wrapped,
                font=font,
                fill=(255, 255, 255, 255),
                spacing=8,
            )
            step_text = f"{timestamp:05.1f}s"
            step_bbox = draw.textbbox((0, 0), step_text, font=small_font)
            badge_width = step_bbox[2] - step_bbox[0] + 26
            badge_height = step_bbox[3] - step_bbox[1] + 14
            badge_x = box_x + box_width - badge_width - 18
            badge_y = box_y - badge_height - 10
            draw.rounded_rectangle(
                (badge_x, badge_y, badge_x + badge_width, badge_y + badge_height),
                radius=16,
                fill=(249, 115, 22, 220),
            )
            draw.text((badge_x + 13, badge_y + 7), step_text, font=small_font, fill=(255, 255, 255, 255))

        encode.stdin.write(image.tobytes())

    decode.stdout.close()
    decode.wait()
    encode.stdin.close()
    encode.wait()

    if decode.returncode != 0:
        raise SystemExit(decode.returncode)
    if encode.returncode != 0:
        raise SystemExit(encode.returncode)


if __name__ == "__main__":
    main()
