from __future__ import annotations

import argparse
import ctypes
import json
import struct
import time
from dataclasses import dataclass
from datetime import datetime, timezone
from pathlib import Path

from balatro_ai.observation import BalatroPaths, BalatroSaveObserver, LightweightCapturePlan


OUTPUT_ROOT = Path("obs_test_output")


@dataclass(frozen=True)
class CaptureTarget:
    left: int
    top: int
    width: int
    height: int
    description: str
    hwnd: int | None = None


def build_parser() -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser(
        description="Inspect Balatro save parsing and lightweight screenshot capture."
    )
    parser.add_argument("--profile", type=int, default=2, help="Balatro profile number to read.")
    parser.add_argument(
        "--poll-interval",
        type=float,
        default=0.5,
        help="Seconds between save-file checks while watching.",
    )
    parser.add_argument(
        "--once",
        action="store_true",
        help="Parse and capture once, then exit.",
    )
    parser.add_argument(
        "--rect",
        nargs=4,
        type=int,
        metavar=("LEFT", "TOP", "WIDTH", "HEIGHT"),
        help="Optional capture rectangle in screen coordinates. Overrides window lookup.",
    )
    parser.add_argument(
        "--window-title",
        default="Balatro",
        help="Substring used to find the Balatro window automatically.",
    )
    parser.add_argument(
        "--output-dir",
        type=Path,
        default=OUTPUT_ROOT,
        help="Where to write screenshots and text output.",
    )
    parser.add_argument(
        "--show",
        action="store_true",
        help="Open the captured full frame in the default image viewer when possible.",
    )
    return parser


def main() -> None:
    args = build_parser().parse_args()
    paths = BalatroPaths(profile=args.profile)
    observer = BalatroSaveObserver(paths=paths)
    run_dir = args.output_dir / datetime.now(timezone.utc).strftime("%Y%m%d_%H%M%S")
    run_dir.mkdir(parents=True, exist_ok=True)

    print(f"[obs_test] profile={args.profile} output={run_dir}")
    print(f"[obs_test] save path: {paths.save_path}")
    print(f"[obs_test] live path: {paths.live_state_path}")

    if not paths.save_path.exists() and not paths.live_state_path.exists():
        print("[obs_test] no save or live-state file exists yet; waiting for one to appear.")

    target = resolve_capture_target(
        manual_rect=tuple(args.rect) if args.rect else None,
        window_title=args.window_title,
    )
    backend = detect_backend(target)
    if backend is None:
        print("[obs_test] no screenshot backend available; running parser-only mode.")
    else:
        print(f"[obs_test] screenshot backend: {backend}")
        if target is not None:
            print(
                "[obs_test] capture target: "
                f"{target.description} "
                f"({target.left}, {target.top}, {target.width}, {target.height})"
            )

    last_stamp: tuple[float | None, float | None] | None = None
    sequence = 0

    while True:
        stamp = current_input_stamp(paths)
        if stamp is None:
            if args.once:
                print("[obs_test] no save or live-state file is available in one-shot mode.")
                return
            time.sleep(args.poll_interval)
            continue

        should_emit = last_stamp is None or stamp != last_stamp

        if should_emit:
            sequence += 1
            last_stamp = stamp
            try:
                observation = observer.observe()
            except Exception as exc:
                print(f"[obs_test] failed to parse save file: {exc}")
                if args.once:
                    return
                time.sleep(args.poll_interval)
                continue
            write_observation(run_dir, sequence, observation)
            print(format_observation(observation))

            if backend is None:
                print("[obs_test] screenshot capture skipped.")
            else:
                capture_result = capture_and_save(
                    backend=backend,
                    capture_plan=observer.capture_plan,
                    target=resolve_capture_target(
                        manual_rect=tuple(args.rect) if args.rect else None,
                        window_title=args.window_title,
                    ),
                    output_dir=run_dir,
                    sequence=sequence,
                    show=args.show,
                )
                print(capture_result)

            if args.once:
                return

        time.sleep(args.poll_interval)


def current_input_stamp(paths: BalatroPaths) -> tuple[float | None, float | None] | None:
    live_mtime = None
    save_mtime = None

    if paths.live_state_path.exists():
        live_mtime = paths.live_state_path.stat().st_mtime
    if paths.save_path.exists():
        save_mtime = paths.save_path.stat().st_mtime

    if live_mtime is None and save_mtime is None:
        return None
    return (live_mtime, save_mtime)


def format_observation(observation: dict[str, object]) -> str:
    # Transitional legacy bridge: this remains a derived debug view downstream of the
    # canonical payload and should not grow new legacy-specific branches.
    score = observation.get("score") or {}
    lines = [
        "",
        "[observation]",
        f"  source: {observation.get('source')}",
        f"  state_id: {observation.get('state_id') if observation.get('state_id') is not None else '-'}",
        f"  interaction_phase: {observation.get('interaction_phase') or '-'}",
        f"  blind_key: {observation.get('blind_key') or '-'}",
        f"  deck_key: {observation.get('deck_key') or '-'}",
        f"  stake_id: {observation.get('stake_id') or '-'}",
        f"  money: {observation.get('money')}",
        f"  score: {score.get('current')}/{score.get('target')}",
        f"  hands_left: {observation.get('hands_left')}",
        f"  discards_left: {observation.get('discards_left')}",
        f"  ante: {observation.get('ante') if observation.get('ante') is not None else '-'}",
        f"  round_count: {observation.get('round_count') if observation.get('round_count') is not None else '-'}",
        f"  joker_slots: {observation.get('joker_slots') if observation.get('joker_slots') is not None else '-'}",
        f"  reroll_cost: {observation.get('reroll_cost') if observation.get('reroll_cost') is not None else '-'}",
        f"  interest: {observation.get('interest') if observation.get('interest') is not None else '-'}",
        f"  inflation: {observation.get('inflation') if observation.get('inflation') is not None else '-'}",
        f"  hand_size: {observation.get('hand_size') if observation.get('hand_size') is not None else '-'}",
        f"  consumable_slots: {observation.get('consumable_slots') if observation.get('consumable_slots') is not None else '-'}",
        f"  joker_count: {observation.get('joker_count') if observation.get('joker_count') is not None else '-'}",
    ]
    jokers = observation.get("jokers") or []
    if jokers:
        lines.append("  jokers:")
        for joker in jokers:
            if not isinstance(joker, dict):
                continue
            extras = []
            if joker.get("rarity"):
                extras.append(f"rarity={joker['rarity']}")
            if joker.get("edition"):
                extras.append(f"edition={joker['edition']}")
            if joker.get("sell_price") is not None:
                extras.append(f"sell_price={joker['sell_price']}")
            stickers = joker.get("stickers")
            if isinstance(stickers, list):
                extras.extend(f"sticker={value}" for value in stickers)
            extra_text = f" [{', '.join(extras)}]" if extras else ""
            lines.append(f"    - {joker.get('key') or '?'}{extra_text}")
    shop_vouchers = observation.get("shop_vouchers") or []
    if shop_vouchers:
        lines.append("  shop_vouchers:")
        for voucher in shop_vouchers:
            if not isinstance(voucher, dict):
                continue
            suffix = f" cost={voucher['cost']}" if voucher.get("cost") is not None else ""
            lines.append(f"    - {voucher.get('key') or '?'}{suffix}")
    vouchers = observation.get("vouchers") or []
    if vouchers:
        lines.append("  vouchers:")
        for voucher in vouchers:
            if not isinstance(voucher, dict):
                continue
            lines.append(f"    - {voucher.get('key') or '?'}")
    consumables = observation.get("consumables") or []
    if consumables:
        lines.append("  consumables:")
        for consumable in consumables:
            if not isinstance(consumable, dict):
                continue
            extras = []
            if consumable.get("cost") is not None:
                extras.append(f"cost={consumable['cost']}")
            if consumable.get("sell_price") is not None:
                extras.append(f"sell_price={consumable['sell_price']}")
            if consumable.get("edition"):
                extras.append(f"edition={consumable['edition']}")
            stickers = consumable.get("stickers")
            if isinstance(stickers, list):
                extras.extend(f"sticker={value}" for value in stickers)
            suffix = f" [{', '.join(extras)}]" if extras else ""
            lines.append(
                f"    - {consumable.get('kind')}: {consumable.get('key') or '?'}{suffix}"
            )
    skip_tags = observation.get("skip_tags") or []
    if skip_tags:
        lines.append("  skip_tags:")
        for skip_tag in skip_tags:
            if not isinstance(skip_tag, dict):
                continue
            suffix = " [claimed=true]" if skip_tag.get("claimed") else ""
            lines.append(f"    - {skip_tag.get('slot')}: {skip_tag.get('key') or '?'}{suffix}")
    tags = observation.get("tags") or []
    if tags:
        lines.append("  tags:")
        for tag in tags:
            if not isinstance(tag, dict):
                continue
            lines.append(f"    - {tag.get('key') or '?'}")
    shop_items = observation.get("shop_items") or []
    if shop_items:
        lines.append("  shop_items:")
        for item in shop_items:
            if not isinstance(item, dict):
                continue
            extras = []
            if item.get("cost") is not None:
                extras.append(f"cost={item['cost']}")
            extra_text = f" [{', '.join(extras)}]" if extras else ""
            lines.append(
                f"    - {item.get('kind')}: {item.get('name') or item.get('key') or '?'}{extra_text}"
            )
    blinds = observation.get("blinds") or []
    if blinds:
        lines.append("  blinds:")
        for blind_choice in blinds:
            if not isinstance(blind_choice, dict):
                continue
            extras = []
            if blind_choice.get("state"):
                extras.append(f"state={blind_choice['state']}")
            if blind_choice.get("tag_key"):
                extras.append(f"tag_key={blind_choice['tag_key']}")
            if blind_choice.get("tag_claimed"):
                extras.append("tag_claimed=true")
            extra_text = f" [{', '.join(extras)}]" if extras else ""
            lines.append(
                f"    - {blind_choice.get('slot')}: {blind_choice.get('key')}{extra_text}"
            )
    cards_in_hand = observation.get("cards_in_hand") or []
    if cards_in_hand:
        lines.append("  cards_in_hand:")
        for card in cards_in_hand:
            if not isinstance(card, dict):
                continue
            modifiers = card.get("modifiers")
            mods = f" [{', '.join(str(value) for value in modifiers)}]" if isinstance(modifiers, list) and modifiers else ""
            extras = []
            if card.get("enhancement"):
                extras.append(f"enh={card['enhancement']}")
            if card.get("edition"):
                extras.append(f"edition={card['edition']}")
            if card.get("seal"):
                extras.append(f"seal={card['seal']}")
            if card.get("facing"):
                extras.append(f"facing={card['facing']}")
            extra_text = f" ({', '.join(extras)})" if extras else ""
            lines.append(
                f"    - {card.get('card_key') or '?'}: {card.get('name') or '?'}{extra_text}{mods}"
            )
    notes = observation.get("notes") or []
    if notes:
        lines.append("  notes:")
        for note in notes:
            lines.append(f"    - {note}")
    return "\n".join(lines)


def write_observation(run_dir: Path, sequence: int, observation) -> None:
    # Transitional legacy bridge: write the canonical payload exactly as observed rather
    # than reintroducing old schema shaping in the harness.
    out_path = run_dir / f"observation_{sequence:04d}.json"
    out_path.write_text(json.dumps(observation, indent=2), encoding="utf-8")


def detect_backend_for_target(target: CaptureTarget | None) -> str | None:
    if target is not None and is_windows() and target.hwnd is not None:
        return "win32_printwindow"
    if target is not None and is_windows():
        return "win32_gdi"
    if try_import_pillow():
        return "pillow"
    if try_import_mss():
        return "mss"
    return None


def detect_backend(target: CaptureTarget | None) -> str | None:
    return detect_backend_for_target(target)


def try_import_pillow() -> bool:
    try:
        from PIL import ImageGrab  # noqa: F401

        return True
    except Exception:
        return False


def try_import_mss() -> bool:
    try:
        import mss  # noqa: F401

        return True
    except Exception:
        return False


def capture_and_save(
    *,
    backend: str,
    capture_plan: LightweightCapturePlan,
    target: CaptureTarget | None,
    output_dir: Path,
    sequence: int,
    show: bool,
) -> str:
    if backend == "win32_printwindow":
        if target is None or target.hwnd is None:
            return "[obs_test] screenshot capture skipped because no Balatro window handle was found."
        try:
            return capture_with_print_window(
                target=target,
                output_dir=output_dir,
                sequence=sequence,
            )
        except Exception as exc:
            fallback_backend = "win32_gdi" if is_windows() else detect_backend_for_target(None)
            if fallback_backend and fallback_backend != "win32_printwindow":
                return capture_and_save(
                    backend=fallback_backend,
                    capture_plan=capture_plan,
                    target=target,
                    output_dir=output_dir,
                    sequence=sequence,
                    show=show,
                )
            return f"[obs_test] screenshot capture failed: {exc}"

    if backend == "win32_gdi":
        if target is None:
            return "[obs_test] screenshot capture skipped because no window target was found."
        try:
            return capture_with_win32_gdi(
                target=target,
                output_dir=output_dir,
                sequence=sequence,
            )
        except Exception as exc:
            fallback_backend = detect_backend_for_target(None)
            if fallback_backend and fallback_backend != "win32_gdi":
                return capture_and_save(
                    backend=fallback_backend,
                    capture_plan=capture_plan,
                    target=None,
                    output_dir=output_dir,
                    sequence=sequence,
                    show=show,
                )
            return f"[obs_test] screenshot capture failed: {exc}"

    if backend == "pillow":
        try:
            return capture_with_pillow(
                capture_plan=capture_plan,
                target=target,
                output_dir=output_dir,
                sequence=sequence,
                show=show,
            )
        except Exception as exc:
            if try_import_mss():
                return capture_with_mss(
                    target=target,
                    output_dir=output_dir,
                    sequence=sequence,
                )
            return f"[obs_test] screenshot capture failed: {exc}"

    try:
        return capture_with_mss(
            target=target,
            output_dir=output_dir,
            sequence=sequence,
        )
    except Exception as exc:
        return f"[obs_test] screenshot capture failed: {exc}"


def capture_with_pillow(
    *,
    capture_plan: LightweightCapturePlan,
    target: CaptureTarget | None,
    output_dir: Path,
    sequence: int,
    show: bool,
) -> str:
    from PIL import ImageGrab

    bbox = rect_to_bbox(target)
    image = ImageGrab.grab(bbox=bbox)
    full_path = output_dir / f"frame_{sequence:04d}_full.png"
    image.save(full_path)

    band_paths = []
    rects = capture_plan.to_rects(*image.size)
    for label, rect in rects.items():
        crop = image.crop((rect.left, rect.top, rect.left + rect.width, rect.top + rect.height))
        crop_path = output_dir / f"frame_{sequence:04d}_{label}.png"
        crop.save(crop_path)
        band_paths.append(crop_path.name)

    if show:
        image.show(title=f"Balatro frame {sequence:04d}")

    return f"[obs_test] saved {full_path.name} and band crops: {', '.join(band_paths)}"


def capture_with_mss(
    *,
    target: CaptureTarget | None,
    output_dir: Path,
    sequence: int,
) -> str:
    import mss
    from mss.tools import to_png

    with mss.mss() as sct:
        monitor = rect_to_monitor(target) if target else sct.monitors[1]
        shot = sct.grab(monitor)
        full_path = output_dir / f"frame_{sequence:04d}_full.png"
        try:
            png_bytes = to_png(shot.rgb, shot.size)
        except TypeError:
            png_bytes = None
            to_png(shot.rgb, shot.size, output=str(full_path))
        if png_bytes is not None:
            full_path.write_bytes(png_bytes)
    return (
        f"[obs_test] saved {full_path.name}. "
        "Band crops require Pillow, so only the full frame was captured."
    )


def capture_with_win32_gdi(
    *,
    target: CaptureTarget,
    output_dir: Path,
    sequence: int,
) -> str:
    image_bytes = grab_screen_rect_bmp(target)
    full_path = output_dir / f"frame_{sequence:04d}_full.bmp"
    full_path.write_bytes(image_bytes)
    return f"[obs_test] saved {full_path.name} from {target.description}."


def capture_with_print_window(
    *,
    target: CaptureTarget,
    output_dir: Path,
    sequence: int,
) -> str:
    image_bytes = grab_window_bmp(target)
    full_path = output_dir / f"frame_{sequence:04d}_full.bmp"
    full_path.write_bytes(image_bytes)
    return f"[obs_test] saved {full_path.name} from {target.description}."


def resolve_capture_target(
    *,
    manual_rect: tuple[int, int, int, int] | None,
    window_title: str,
) -> CaptureTarget | None:
    if manual_rect is not None:
        left, top, width, height = manual_rect
        return CaptureTarget(
            left=left,
            top=top,
            width=width,
            height=height,
            description="manual rect",
            hwnd=None,
        )

    if not is_windows():
        return None
    return find_window_target(window_title)


def find_window_target(window_title: str) -> CaptureTarget | None:
    user32 = ctypes.windll.user32
    try:
        user32.SetProcessDPIAware()
    except AttributeError:
        pass

    class RECT(ctypes.Structure):
        _fields_ = [
            ("left", ctypes.c_long),
            ("top", ctypes.c_long),
            ("right", ctypes.c_long),
            ("bottom", ctypes.c_long),
        ]

    callback_type = ctypes.WINFUNCTYPE(ctypes.c_bool, ctypes.c_void_p, ctypes.c_void_p)
    user32.EnumWindows.argtypes = [callback_type, ctypes.c_void_p]
    user32.EnumWindows.restype = ctypes.c_bool
    user32.IsWindowVisible.argtypes = [ctypes.c_void_p]
    user32.IsWindowVisible.restype = ctypes.c_bool
    user32.GetWindowTextLengthW.argtypes = [ctypes.c_void_p]
    user32.GetWindowTextLengthW.restype = ctypes.c_int
    user32.GetWindowTextW.argtypes = [ctypes.c_void_p, ctypes.c_wchar_p, ctypes.c_int]
    user32.GetWindowTextW.restype = ctypes.c_int
    user32.GetWindowRect.argtypes = [ctypes.c_void_p, ctypes.POINTER(RECT)]
    user32.GetWindowRect.restype = ctypes.c_bool

    matches: list[CaptureTarget] = []
    title_query = window_title.lower()

    @callback_type
    def callback(hwnd, _lparam):
        if not user32.IsWindowVisible(hwnd):
            return True
        length = user32.GetWindowTextLengthW(hwnd)
        if length == 0:
            return True
        buffer = ctypes.create_unicode_buffer(length + 1)
        user32.GetWindowTextW(hwnd, buffer, len(buffer))
        title = buffer.value.strip()
        if not title or title_query not in title.lower():
            return True

        rect = RECT()
        if not user32.GetWindowRect(hwnd, ctypes.byref(rect)):
            return True
        width = rect.right - rect.left
        height = rect.bottom - rect.top
        if width <= 0 or height <= 0:
            return True

        matches.append(
            CaptureTarget(
                left=rect.left,
                top=rect.top,
                width=width,
                height=height,
                description=f'window "{title}"',
                hwnd=int(hwnd),
            )
        )
        return True

    user32.EnumWindows(callback, 0)
    if not matches:
        return None
    matches.sort(key=lambda item: item.width * item.height, reverse=True)
    return matches[0]


def grab_screen_rect_bmp(target: CaptureTarget) -> bytes:
    user32 = ctypes.windll.user32
    gdi32 = ctypes.windll.gdi32

    user32.GetDC.argtypes = [ctypes.c_void_p]
    user32.GetDC.restype = ctypes.c_void_p
    user32.ReleaseDC.argtypes = [ctypes.c_void_p, ctypes.c_void_p]
    user32.ReleaseDC.restype = ctypes.c_int
    gdi32.CreateCompatibleDC.argtypes = [ctypes.c_void_p]
    gdi32.CreateCompatibleDC.restype = ctypes.c_void_p
    gdi32.CreateCompatibleBitmap.argtypes = [ctypes.c_void_p, ctypes.c_int, ctypes.c_int]
    gdi32.CreateCompatibleBitmap.restype = ctypes.c_void_p
    gdi32.SelectObject.argtypes = [ctypes.c_void_p, ctypes.c_void_p]
    gdi32.SelectObject.restype = ctypes.c_void_p
    gdi32.BitBlt.argtypes = [
        ctypes.c_void_p,
        ctypes.c_int,
        ctypes.c_int,
        ctypes.c_int,
        ctypes.c_int,
        ctypes.c_void_p,
        ctypes.c_int,
        ctypes.c_int,
        ctypes.c_uint32,
    ]
    gdi32.BitBlt.restype = ctypes.c_bool
    gdi32.DeleteObject.argtypes = [ctypes.c_void_p]
    gdi32.DeleteObject.restype = ctypes.c_bool
    gdi32.DeleteDC.argtypes = [ctypes.c_void_p]
    gdi32.DeleteDC.restype = ctypes.c_bool

    screen_dc = user32.GetDC(0)
    if not screen_dc:
        raise RuntimeError("GetDC failed.")

    mem_dc = gdi32.CreateCompatibleDC(screen_dc)
    if not mem_dc:
        user32.ReleaseDC(0, screen_dc)
        raise RuntimeError("CreateCompatibleDC failed.")

    bitmap = gdi32.CreateCompatibleBitmap(screen_dc, target.width, target.height)
    if not bitmap:
        gdi32.DeleteDC(mem_dc)
        user32.ReleaseDC(0, screen_dc)
        raise RuntimeError("CreateCompatibleBitmap failed.")

    old_bitmap = gdi32.SelectObject(mem_dc, bitmap)
    srccopy = 0x00CC0020
    ok = gdi32.BitBlt(
        mem_dc,
        0,
        0,
        target.width,
        target.height,
        screen_dc,
        target.left,
        target.top,
        srccopy,
    )
    if not ok:
        gdi32.SelectObject(mem_dc, old_bitmap)
        gdi32.DeleteObject(bitmap)
        gdi32.DeleteDC(mem_dc)
        user32.ReleaseDC(0, screen_dc)
        raise RuntimeError("BitBlt failed.")

    class BITMAPINFOHEADER(ctypes.Structure):
        _fields_ = [
            ("biSize", ctypes.c_uint32),
            ("biWidth", ctypes.c_int32),
            ("biHeight", ctypes.c_int32),
            ("biPlanes", ctypes.c_uint16),
            ("biBitCount", ctypes.c_uint16),
            ("biCompression", ctypes.c_uint32),
            ("biSizeImage", ctypes.c_uint32),
            ("biXPelsPerMeter", ctypes.c_int32),
            ("biYPelsPerMeter", ctypes.c_int32),
            ("biClrUsed", ctypes.c_uint32),
            ("biClrImportant", ctypes.c_uint32),
        ]

    class BITMAPINFO(ctypes.Structure):
        _fields_ = [
            ("bmiHeader", BITMAPINFOHEADER),
            ("bmiColors", ctypes.c_uint32 * 3),
        ]

    gdi32.GetDIBits.argtypes = [
        ctypes.c_void_p,
        ctypes.c_void_p,
        ctypes.c_uint,
        ctypes.c_uint,
        ctypes.c_void_p,
        ctypes.POINTER(BITMAPINFO),
        ctypes.c_uint,
    ]
    gdi32.GetDIBits.restype = ctypes.c_int

    row_stride = target.width * 4
    pixel_bytes = row_stride * target.height
    buffer = ctypes.create_string_buffer(pixel_bytes)

    bmi = BITMAPINFO()
    bmi.bmiHeader.biSize = ctypes.sizeof(BITMAPINFOHEADER)
    bmi.bmiHeader.biWidth = target.width
    bmi.bmiHeader.biHeight = target.height
    bmi.bmiHeader.biPlanes = 1
    bmi.bmiHeader.biBitCount = 32
    bmi.bmiHeader.biCompression = 0
    bmi.bmiHeader.biSizeImage = pixel_bytes

    dib_rgb_colors = 0
    scan_lines = gdi32.GetDIBits(
        mem_dc,
        bitmap,
        0,
        target.height,
        buffer,
        ctypes.byref(bmi),
        dib_rgb_colors,
    )

    gdi32.SelectObject(mem_dc, old_bitmap)
    gdi32.DeleteObject(bitmap)
    gdi32.DeleteDC(mem_dc)
    user32.ReleaseDC(0, screen_dc)

    if scan_lines != target.height:
        raise RuntimeError("GetDIBits failed.")

    file_header_size = 14
    info_header_size = ctypes.sizeof(BITMAPINFOHEADER)
    offset = file_header_size + info_header_size
    file_size = offset + pixel_bytes

    file_header = struct.pack(
        "<2sIHHI",
        b"BM",
        file_size,
        0,
        0,
        offset,
    )
    info_header = struct.pack(
        "<IIIHHIIIIII",
        info_header_size,
        target.width,
        target.height,
        1,
        32,
        0,
        pixel_bytes,
        0,
        0,
        0,
        0,
    )
    return file_header + info_header + buffer.raw


def grab_window_bmp(target: CaptureTarget) -> bytes:
    if target.hwnd is None:
        raise RuntimeError("PrintWindow requires a real window handle.")

    user32 = ctypes.windll.user32
    gdi32 = ctypes.windll.gdi32

    user32.GetWindowDC.argtypes = [ctypes.c_void_p]
    user32.GetWindowDC.restype = ctypes.c_void_p
    user32.ReleaseDC.argtypes = [ctypes.c_void_p, ctypes.c_void_p]
    user32.ReleaseDC.restype = ctypes.c_int
    user32.PrintWindow.argtypes = [ctypes.c_void_p, ctypes.c_void_p, ctypes.c_uint]
    user32.PrintWindow.restype = ctypes.c_bool
    gdi32.CreateCompatibleDC.argtypes = [ctypes.c_void_p]
    gdi32.CreateCompatibleDC.restype = ctypes.c_void_p
    gdi32.CreateCompatibleBitmap.argtypes = [ctypes.c_void_p, ctypes.c_int, ctypes.c_int]
    gdi32.CreateCompatibleBitmap.restype = ctypes.c_void_p
    gdi32.SelectObject.argtypes = [ctypes.c_void_p, ctypes.c_void_p]
    gdi32.SelectObject.restype = ctypes.c_void_p
    gdi32.DeleteObject.argtypes = [ctypes.c_void_p]
    gdi32.DeleteObject.restype = ctypes.c_bool
    gdi32.DeleteDC.argtypes = [ctypes.c_void_p]
    gdi32.DeleteDC.restype = ctypes.c_bool

    hwnd = ctypes.c_void_p(target.hwnd)
    window_dc = user32.GetWindowDC(hwnd)
    if not window_dc:
        raise RuntimeError("GetWindowDC failed.")

    mem_dc = gdi32.CreateCompatibleDC(window_dc)
    if not mem_dc:
        user32.ReleaseDC(hwnd, window_dc)
        raise RuntimeError("CreateCompatibleDC failed.")

    bitmap = gdi32.CreateCompatibleBitmap(window_dc, target.width, target.height)
    if not bitmap:
        gdi32.DeleteDC(mem_dc)
        user32.ReleaseDC(hwnd, window_dc)
        raise RuntimeError("CreateCompatibleBitmap failed.")

    old_bitmap = gdi32.SelectObject(mem_dc, bitmap)

    # PW_RENDERFULLCONTENT asks Windows for the full window contents when supported.
    pw_renderfullcontent = 0x00000002
    ok = user32.PrintWindow(hwnd, mem_dc, pw_renderfullcontent)
    if not ok:
        ok = user32.PrintWindow(hwnd, mem_dc, 0)

    if not ok:
        gdi32.SelectObject(mem_dc, old_bitmap)
        gdi32.DeleteObject(bitmap)
        gdi32.DeleteDC(mem_dc)
        user32.ReleaseDC(hwnd, window_dc)
        raise RuntimeError("PrintWindow failed.")

    result = bitmap_to_bmp_bytes(
        gdi32=gdi32,
        mem_dc=mem_dc,
        bitmap=bitmap,
        width=target.width,
        height=target.height,
    )

    gdi32.SelectObject(mem_dc, old_bitmap)
    gdi32.DeleteObject(bitmap)
    gdi32.DeleteDC(mem_dc)
    user32.ReleaseDC(hwnd, window_dc)
    return result


def bitmap_to_bmp_bytes(
    *,
    gdi32,
    mem_dc,
    bitmap,
    width: int,
    height: int,
) -> bytes:
    class BITMAPINFOHEADER(ctypes.Structure):
        _fields_ = [
            ("biSize", ctypes.c_uint32),
            ("biWidth", ctypes.c_int32),
            ("biHeight", ctypes.c_int32),
            ("biPlanes", ctypes.c_uint16),
            ("biBitCount", ctypes.c_uint16),
            ("biCompression", ctypes.c_uint32),
            ("biSizeImage", ctypes.c_uint32),
            ("biXPelsPerMeter", ctypes.c_int32),
            ("biYPelsPerMeter", ctypes.c_int32),
            ("biClrUsed", ctypes.c_uint32),
            ("biClrImportant", ctypes.c_uint32),
        ]

    class BITMAPINFO(ctypes.Structure):
        _fields_ = [
            ("bmiHeader", BITMAPINFOHEADER),
            ("bmiColors", ctypes.c_uint32 * 3),
        ]

    gdi32.GetDIBits.argtypes = [
        ctypes.c_void_p,
        ctypes.c_void_p,
        ctypes.c_uint,
        ctypes.c_uint,
        ctypes.c_void_p,
        ctypes.POINTER(BITMAPINFO),
        ctypes.c_uint,
    ]
    gdi32.GetDIBits.restype = ctypes.c_int

    row_stride = width * 4
    pixel_bytes = row_stride * height
    buffer = ctypes.create_string_buffer(pixel_bytes)

    bmi = BITMAPINFO()
    bmi.bmiHeader.biSize = ctypes.sizeof(BITMAPINFOHEADER)
    bmi.bmiHeader.biWidth = width
    bmi.bmiHeader.biHeight = height
    bmi.bmiHeader.biPlanes = 1
    bmi.bmiHeader.biBitCount = 32
    bmi.bmiHeader.biCompression = 0
    bmi.bmiHeader.biSizeImage = pixel_bytes

    dib_rgb_colors = 0
    scan_lines = gdi32.GetDIBits(
        mem_dc,
        bitmap,
        0,
        height,
        buffer,
        ctypes.byref(bmi),
        dib_rgb_colors,
    )
    if scan_lines != height:
        raise RuntimeError("GetDIBits failed.")

    file_header_size = 14
    info_header_size = ctypes.sizeof(BITMAPINFOHEADER)
    offset = file_header_size + info_header_size
    file_size = offset + pixel_bytes

    file_header = struct.pack(
        "<2sIHHI",
        b"BM",
        file_size,
        0,
        0,
        offset,
    )
    info_header = struct.pack(
        "<IIIHHIIIIII",
        info_header_size,
        width,
        height,
        1,
        32,
        0,
        pixel_bytes,
        0,
        0,
        0,
        0,
    )
    return file_header + info_header + buffer.raw


def rect_to_bbox(target: CaptureTarget | None):
    if target is None:
        return None
    left, top, width, height = target.left, target.top, target.width, target.height
    return (left, top, left + width, top + height)


def rect_to_monitor(target: CaptureTarget) -> dict[str, int]:
    left, top, width, height = target.left, target.top, target.width, target.height
    return {"left": left, "top": top, "width": width, "height": height}


def is_windows() -> bool:
    return hasattr(ctypes, "windll") and hasattr(ctypes.windll, "user32")


if __name__ == "__main__":
    main()
