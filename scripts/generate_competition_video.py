"""generate_competition_video — 采集中控台页面并生成答辩演示视频。

所属层：scripts
依赖：playwright, Pillow, imageio, imageio-ffmpeg, Windows SAPI
对接算法层：N/A
"""
import base64
import subprocess
import wave
from pathlib import Path
from typing import Dict, List, Tuple

import imageio.v2 as imageio
import imageio_ffmpeg
import numpy as np
from PIL import Image, ImageDraw, ImageFont
from playwright.sync_api import sync_playwright

ROOT = Path(__file__).resolve().parents[1]
ASSETS = ROOT / "deliverables" / "assets"
DELIVERABLES = ROOT / "deliverables"
CHROME = Path(r"C:\Program Files\Google\Chrome\Application\chrome.exe")
VIDEO_BASE = DELIVERABLES / "TrafficGraph_演示视频_无声.mp4"
VIDEO_FINAL = DELIVERABLES / "TrafficGraph_演示视频.mp4"
AUDIO = DELIVERABLES / "TrafficGraph_演示视频_旁白.wav"

WIDTH = 1920
HEIGHT = 1080
FPS = 24
FONT_PATH = Path(r"C:\Windows\Fonts\simhei.ttf")


SCENES = [
    {
        "key": "cover",
        "title": "TrafficGraph 智慧交通指挥 Agent",
        "caption": "上海市智慧交通指挥中心",
        "narration": (
            "各位评委老师好，下面介绍 TrafficGraph 智慧交通指挥 Agent。"
            "系统面向上海市交通指挥场景，目标是让实时数据、交通知识、信号优化、"
            "事件处置和报表导出在一个中控平台中协同工作。"
        ),
    },
    {
        "key": "overview",
        "title": "态势总览：一屏掌握城市运行状态",
        "caption": "拥堵指数、平均车速、活跃事件、Top5 与实时路网",
        "narration": (
            "首先进入态势总览。页面将城市拥堵指数、平均车速、活跃事件和瓶颈路口"
            "集中在一个屏幕中，同时展示上海市五条干线及二十四个监控路口的实时运行状态。"
            "不同饱和度使用不同颜色标识，便于值班人员快速定位异常。"
        ),
    },
    {
        "key": "network",
        "title": "路网监控：定位路口和诊断原因",
        "caption": "支持路口搜索、干线筛选、台账查看和单点诊断",
        "narration": (
            "第二个视图是路网监控。这里可以搜索路口名称或编号，也可以按干线筛选。"
            "表格展示服务水平、饱和度、延误、排队和当前相位。"
            "点击任意路口后，系统会给出进口道排队和运行状态诊断。"
        ),
    },
    {
        "key": "signals",
        "title": "信号控制：配时与绿波协同",
        "caption": "查看周期、相位、协调组和 Webster 优化建议",
        "narration": (
            "信号控制视图展示五条干线的绿波状态和带宽。"
            "选择具体路口后，可以看到当前配时方案、周期、相位差、协调组和每个相位的绿灯时间。"
            "系统同时给出 Webster 周期、绿信比或相位差优化建议，并保留最小绿灯、"
            "行人过街和协调同步等安全约束。"
        ),
    },
    {
        "key": "incidents",
        "title": "事件处置：统一事件队列和调度资源",
        "caption": "严重度、占道情况、恢复时间和调度时间线",
        "narration": (
            "事件处置视图把事故、车辆抛锚、施工和临时管制统一到事件队列中。"
            "页面展示严重度、位置、占道情况、预计恢复时间和处置状态，"
            "同时给出警力、拖车和信号保障资源的可调度状态。"
        ),
    },
    {
        "key": "report",
        "title": "数据可视化与智能报表",
        "caption": "表格、柱状图、折线图、环形图和 CSV 下载",
        "narration": (
            "系统支持一键导出当前视图。报告同时包含数据表格、可视化图表和 CSV 文件。"
            "例如态势总览可以导出拥堵 Top5，信号控制可以导出相位和绿灯时间，"
            "事件页面可以导出事件明细和严重度分布。"
        ),
    },
    {
        "key": "agent",
        "title": "Agent Copilot：自然语言交通研判",
        "caption": "工具调用、知识来源、流式回答和人工确认动作",
        "narration": (
            "右侧是指挥 Copilot。用户可以直接用自然语言提问，例如现在上海市哪里最堵。"
            "Agent 会自动选择交通数据工具，调用实时仿真数据并生成研判报告。"
            "页面动作不会自动执行，只会生成待确认按钮，保证指挥过程可控。"
        ),
    },
    {
        "key": "closing",
        "title": "从数据查询到指挥决策辅助",
        "caption": "可复现、可解释、可扩展、安全可控",
        "narration": (
            "TrafficGraph 将交通数据、专业知识、信号分析和事件调度统一到一个 Agent 中，"
            "实现从自然语言查询到可视化研判和报表输出的完整闭环。"
            "系统坚持只分析和建议，不直接控制真实信号，保证比赛演示和实际落地都安全可控。"
            "谢谢各位评委。"
        ),
    },
]


def ensure_assets() -> None:
    """确保输出目录存在。"""
    ASSETS.mkdir(parents=True, exist_ok=True)
    DELIVERABLES.mkdir(parents=True, exist_ok=True)


def capture_screenshots() -> Dict[str, Path]:
    """使用系统 Chrome 采集各工作区截图。"""
    if not CHROME.exists():
        raise FileNotFoundError(f"Chrome 不存在: {CHROME}")

    outputs = {
        "overview": ASSETS / "overview.png",
        "network": ASSETS / "network.png",
        "signals": ASSETS / "signals.png",
        "incidents": ASSETS / "incidents.png",
        "report": ASSETS / "report.png",
        "agent": ASSETS / "agent.png",
    }

    with sync_playwright() as playwright:
        browser = playwright.chromium.launch(
            executable_path=str(CHROME),
            headless=True,
        )
        context = browser.new_context(
            viewport={"width": WIDTH, "height": HEIGHT},
            device_scale_factor=1,
        )
        page = context.new_page()
        page.goto("http://127.0.0.1:8000/", wait_until="networkidle")
        page.wait_for_timeout(2000)
        page.screenshot(path=str(outputs["overview"]), full_page=False)

        page.click('button[data-view="network"]')
        page.wait_for_timeout(1200)
        page.screenshot(path=str(outputs["network"]), full_page=False)

        page.click('button[data-view="signals"]')
        page.wait_for_timeout(2500)
        page.screenshot(path=str(outputs["signals"]), full_page=False)

        page.click('button[data-view="incidents"]')
        page.wait_for_timeout(1200)
        page.screenshot(path=str(outputs["incidents"]), full_page=False)

        page.click('button[data-view="overview"]')
        page.wait_for_timeout(500)
        page.click("#export-view")
        page.wait_for_selector("#report-drawer.is-open", timeout=15000)
        page.wait_for_timeout(800)
        page.screenshot(path=str(outputs["report"]), full_page=False)
        page.click("#close-report")

        page.fill("#chat-input", "现在上海市哪里最堵？")
        page.click("#send-button")
        page.wait_for_timeout(1000)
        try:
            page.wait_for_function(
                "document.querySelector('#agent-state')?.textContent.includes('等待指令')",
                timeout=120000,
            )
        except Exception:
            pass
        page.screenshot(path=str(outputs["agent"]), full_page=False)
        context.close()
        browser.close()
    return outputs


def synthesize_windows_wav(text: str, output_path: Path) -> None:
    """使用本机中文 SAPI 生成旁白 WAV。"""
    encoded = base64.b64encode(text.encode("utf-8")).decode("ascii")
    escaped_path = str(output_path).replace("'", "''")
    command = f"""
$ErrorActionPreference = 'Stop'
Add-Type -AssemblyName System.Speech
$text = [Text.Encoding]::UTF8.GetString([Convert]::FromBase64String('{encoded}'))
$speaker = New-Object System.Speech.Synthesis.SpeechSynthesizer
$voice = $speaker.GetInstalledVoices() | Where-Object {{ $_.VoiceInfo.Culture.Name -eq 'zh-CN' }} | Select-Object -First 1
if ($voice) {{ $speaker.SelectVoice($voice.VoiceInfo.Name) }}
$speaker.Rate = 0
$speaker.Volume = 100
$speaker.SetOutputToWaveFile('{escaped_path}')
$speaker.Speak($text)
$speaker.Dispose()
"""
    subprocess.run(
        [
            r"C:\WINDOWS\System32\WindowsPowerShell\v1.0\powershell.exe",
            "-NoProfile",
            "-Command",
            command,
        ],
        check=True,
        capture_output=True,
    )


def wav_info(path: Path) -> Tuple[int, int, int, int, bytes]:
    """读取 WAV 参数和音频帧。"""
    with wave.open(str(path), "rb") as source:
        return (
            source.getnchannels(),
            source.getsampwidth(),
            source.getframerate(),
            source.getnframes(),
            source.readframes(source.getnframes()),
        )


def audio_duration(path: Path) -> float:
    """返回 WAV 秒数。"""
    _channels, _sample_width, frame_rate, frames, _ = wav_info(path)
    return frames / float(frame_rate)


def make_cover_frame() -> Image.Image:
    """生成视频封面帧。"""
    image = Image.new("RGB", (WIDTH, HEIGHT), "#10231B")
    draw = ImageDraw.Draw(image)
    draw.rectangle((140, 170, 154, 470), fill="#17A578")
    title_font = ImageFont.truetype(str(FONT_PATH), 72)
    sub_font = ImageFont.truetype(str(FONT_PATH), 36)
    small_font = ImageFont.truetype(str(FONT_PATH), 24)
    draw.text((205, 190), "TrafficGraph", font=title_font, fill="#FFFFFF")
    draw.text((205, 295), "上海市智慧交通指挥 Agent", font=sub_font, fill="#D9E9E1")
    draw.text(
        (208, 370),
        "多源态势融合 · 信号优化 · 事件处置 · 数据可视化 · 智能报表",
        font=small_font,
        fill="#8EB5A4",
    )
    draw.text((208, 905), "智慧城市竞赛答辩演示", font=small_font, fill="#D9E9E1")
    return image


def make_screenshot_frame(path: Path, scene: Dict[str, str], index: int) -> Image.Image:
    """在截图上叠加标题和说明。"""
    image = Image.open(path).convert("RGB")
    image = image.resize((WIDTH, HEIGHT), Image.Resampling.LANCZOS)
    overlay = Image.new("RGBA", (WIDTH, HEIGHT), (0, 0, 0, 0))
    draw = ImageDraw.Draw(overlay)
    draw.rectangle((0, HEIGHT - 132, WIDTH, HEIGHT), fill=(8, 20, 15, 214))
    draw.rectangle((0, HEIGHT - 136, WIDTH, HEIGHT - 130), fill=(23, 165, 120, 255))
    title_font = ImageFont.truetype(str(FONT_PATH), 32)
    caption_font = ImageFont.truetype(str(FONT_PATH), 20)
    draw.text((46, HEIGHT - 112), scene["title"], font=title_font, fill="#FFFFFF")
    draw.text((47, HEIGHT - 65), scene["caption"], font=caption_font, fill="#BED2C8")
    draw.text((WIDTH - 98, 28), f"{index:02d}", font=caption_font, fill="#617D6F")
    return Image.alpha_composite(image.convert("RGBA"), overlay).convert("RGB")


def build_audio(scene_durations: List[float], scene_audio: List[Path]) -> None:
    """按视频场景时长拼接旁白和静音。"""
    template = None
    output_frames = bytearray()
    for duration, audio_path in zip(scene_durations, scene_audio):
        channels, sample_width, frame_rate, frames, frames_bytes = wav_info(audio_path)
        current = (channels, sample_width, frame_rate)
        if template is None:
            template = current
        elif current != template:
            raise ValueError("旁白 WAV 参数不一致")
        output_frames.extend(frames_bytes)
        spoken = frames / float(frame_rate)
        silence_seconds = max(0.0, duration - spoken)
        output_frames.extend(b"\x00" * int(silence_seconds * frame_rate * channels * sample_width))

    if template is None:
        raise ValueError("没有旁白音频")
    channels, sample_width, frame_rate = template
    with wave.open(str(AUDIO), "wb") as target:
        target.setnchannels(channels)
        target.setsampwidth(sample_width)
        target.setframerate(frame_rate)
        target.writeframes(bytes(output_frames))


def create_video(screenshots: Dict[str, Path]) -> None:
    """生成带旁白的 MP4 演示视频。"""
    scene_audio: List[Path] = []
    scene_durations: List[float] = []
    for index, scene in enumerate(SCENES, start=1):
        audio_path = ASSETS / f"narration_{index:02d}.wav"
        synthesize_windows_wav(scene["narration"], audio_path)
        duration = max(5.5, audio_duration(audio_path) + 0.8)
        scene_audio.append(audio_path)
        scene_durations.append(duration)

    build_audio(scene_durations, scene_audio)
    writer = imageio.get_writer(
        str(VIDEO_BASE),
        fps=FPS,
        codec="libx264",
        quality=7,
        pixelformat="yuv420p",
        macro_block_size=8,
    )
    try:
        for index, (scene, duration) in enumerate(zip(SCENES, scene_durations), start=1):
            if scene["key"] == "cover":
                frame = make_cover_frame()
            elif scene["key"] == "closing":
                frame = make_cover_frame()
                draw = ImageDraw.Draw(frame)
                draw.rectangle((0, 0, WIDTH, HEIGHT), fill=(15, 35, 27))
                draw.rectangle((140, 230, 154, 500), fill="#17A578")
                draw.text(
                    (205, 250),
                    "从数据查询到指挥决策辅助",
                    font=ImageFont.truetype(str(FONT_PATH), 54),
                    fill="#FFFFFF",
                )
                draw.text(
                    (208, 345),
                    "可复现 · 可解释 · 可扩展 · 安全可控",
                    font=ImageFont.truetype(str(FONT_PATH), 30),
                    fill="#BFD5C9",
                )
                draw.text(
                    (208, 900),
                    "谢谢各位评委",
                    font=ImageFont.truetype(str(FONT_PATH), 28),
                    fill="#17C58F",
                )
            else:
                frame = make_screenshot_frame(screenshots[scene["key"]], scene, index - 1)

            frame_array = np.asarray(frame)
            frame_count = int(duration * FPS)
            fade_frames = min(10, max(1, frame_count // 8))
            for number in range(frame_count):
                if number < fade_frames:
                    ratio = number / fade_frames
                    blended = (frame_array * ratio).astype(np.uint8)
                elif number >= frame_count - fade_frames:
                    ratio = (frame_count - number - 1) / fade_frames
                    blended = (frame_array * ratio).astype(np.uint8)
                else:
                    blended = frame_array
                writer.append_data(blended)
    finally:
        writer.close()

    ffmpeg = imageio_ffmpeg.get_ffmpeg_exe()
    subprocess.run(
        [
            ffmpeg,
            "-y",
            "-i",
            str(VIDEO_BASE),
            "-i",
            str(AUDIO),
            "-c:v",
            "copy",
            "-c:a",
            "aac",
            "-shortest",
            str(VIDEO_FINAL),
        ],
        check=True,
    )


if __name__ == "__main__":
    ensure_assets()
    captures = capture_screenshots()
    create_video(captures)
    print(f"Video generated: {VIDEO_FINAL}")
