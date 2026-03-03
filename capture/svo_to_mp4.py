#!/usr/bin/env python3
"""
Convert SVO file to MP4 preview using ZED SDK.
Extracts the left camera view and encodes to browser-playable MP4.
Runs as a separate process so it doesn't block live capture.
Skips frames and caps length for Jetson Nano memory constraints.
"""

import os
import sys
import subprocess
import traceback

# Fix for Jetson Nano Cortex-A57 OpenBLAS
os.environ['OPENBLAS_CORETYPE'] = 'ARMV8'

import pyzed.sl as sl

# Preview limits for Jetson Nano (4GB RAM)
FRAME_SKIP = 3         # Only encode every Nth frame
MAX_OUTPUT_FRAMES = 900  # Max frames in preview (~30s at 30fps output)
OUTPUT_FPS = 10        # Lower output FPS to reduce file size
PREVIEW_WIDTH = 640
PREVIEW_HEIGHT = 360


def convert(svoPath, mp4Path=None):
    """Convert SVO file to MP4 preview"""
    if mp4Path is None:
        mp4Path = svoPath.replace('.svo', '_preview.mp4')

    print("Converting: {} -> {}".format(svoPath, mp4Path))

    # Remove stale 0-byte preview if exists
    if os.path.exists(mp4Path) and os.path.getsize(mp4Path) == 0:
        os.remove(mp4Path)

    cam = sl.Camera()
    params = sl.InitParameters()
    params.set_from_svo_file(svoPath)
    params.svo_real_time_mode = False
    # Disable depth to save RAM during preview conversion
    params.depth_mode = sl.DEPTH_MODE.NONE

    err = cam.open(params)
    if err != sl.ERROR_CODE.SUCCESS:
        print("Failed to open SVO: {}".format(err))
        return False

    info = cam.get_camera_information()
    res = info.camera_resolution
    w, h = res.width, res.height
    totalFrames = cam.get_svo_number_of_frames()
    print("SVO resolution: {}x{}, total frames: {}".format(w, h, totalFrames))

    # Auto-adjust frame skip for very long recordings
    frameSkip = FRAME_SKIP
    if totalFrames > MAX_OUTPUT_FRAMES * FRAME_SKIP:
        frameSkip = max(FRAME_SKIP, totalFrames // MAX_OUTPUT_FRAMES)
    print("Frame skip: {} (output ~{} frames)".format(
        frameSkip, min(MAX_OUTPUT_FRAMES, totalFrames // frameSkip)))

    # Build encoder command - try ffmpeg first, fall back to GStreamer
    cmd = None
    encoder = None

    try:
        subprocess.run(
            ["ffmpeg", "-version"],
            stdout=subprocess.PIPE, stderr=subprocess.PIPE, check=True)
        encoder = "ffmpeg"
        cmd = [
            "ffmpeg", "-y", "-loglevel", "warning",
            "-f", "rawvideo", "-vcodec", "rawvideo",
            "-s", "{}x{}".format(w, h),
            "-pix_fmt", "bgra", "-r", str(OUTPUT_FPS),
            "-i", "-",
            "-vf", "scale={}:{}".format(PREVIEW_WIDTH, PREVIEW_HEIGHT),
            "-c:v", "libx264", "-preset", "ultrafast",
            "-profile:v", "baseline", "-pix_fmt", "yuv420p",
            "-movflags", "+faststart",
            mp4Path
        ]
    except (subprocess.CalledProcessError, FileNotFoundError):
        encoder = "gstreamer"
        blocksize = w * h * 4
        cmd = [
            "gst-launch-1.0", "-e",
            "fdsrc", "blocksize={}".format(blocksize), "!",
            "rawvideoparse", "use-sink-caps=false",
            "width={}".format(w), "height={}".format(h),
            "format=bgra", "framerate={}/1".format(OUTPUT_FPS), "!",
            "videoconvert", "!",
            "videoscale", "!",
            "video/x-raw,width={},height={}".format(
                PREVIEW_WIDTH, PREVIEW_HEIGHT), "!",
            "x264enc", "tune=zerolatency", "bitrate=1500",
            "speed-preset=ultrafast", "!",
            "video/x-h264,profile=baseline", "!",
            "mp4mux", "faststart=true", "!",
            "filesink", "location={}".format(mp4Path)
        ]

    print("Using encoder: {}".format(encoder))
    proc = subprocess.Popen(
        cmd, stdin=subprocess.PIPE,
        stdout=subprocess.PIPE, stderr=subprocess.PIPE)

    image = sl.Mat()
    grabbed = 0
    written = 0

    try:
        while written < MAX_OUTPUT_FRAMES:
            err = cam.grab()
            if err == sl.ERROR_CODE.SUCCESS:
                grabbed += 1
                # Skip frames to reduce load
                if grabbed % frameSkip != 0:
                    continue
                cam.retrieve_image(image, sl.VIEW.LEFT)
                frame = image.get_data()
                if frame is None:
                    continue
                try:
                    proc.stdin.write(frame.tobytes())
                    written += 1
                    if written % 100 == 0:
                        print("  Written {}/{} frames (grabbed {})".format(
                            written, MAX_OUTPUT_FRAMES, grabbed))
                except BrokenPipeError:
                    stderr = proc.stderr.read().decode('utf-8', errors='replace')
                    print("Encoder pipe broken. stderr: {}".format(stderr))
                    break
            elif err == sl.ERROR_CODE.END_OF_SVOFILE_REACHED:
                break
            else:
                print("Grab error at frame {}: {}".format(grabbed, err))
                break
    except Exception as e:
        print("Error during conversion: {}".format(e))
        traceback.print_exc()

    try:
        proc.stdin.close()
    except Exception:
        pass
    try:
        proc.wait(timeout=120)
        if proc.returncode != 0:
            stderr = proc.stderr.read().decode('utf-8', errors='replace')
            print("Encoder exited with code {}. stderr: {}".format(
                proc.returncode, stderr))
    except subprocess.TimeoutExpired:
        proc.kill()
        proc.wait()
        print("Encoder timed out after 120s")

    cam.close()

    if os.path.exists(mp4Path) and os.path.getsize(mp4Path) > 0:
        sizeMb = os.path.getsize(mp4Path) / (1024 * 1024)
        print("Preview saved: {} ({:.1f} MB, {} frames written)".format(
            mp4Path, sizeMb, written))
        return True
    else:
        # Clean up 0-byte file
        if os.path.exists(mp4Path):
            os.remove(mp4Path)
        print("Failed to create preview MP4 ({} frames grabbed, {} written)".format(
            grabbed, written))
        return False


if __name__ == "__main__":
    if len(sys.argv) < 2:
        print("Usage: svo_to_mp4.py <svo_file> [mp4_file]")
        sys.exit(1)
    svoFile = sys.argv[1]
    mp4File = sys.argv[2] if len(sys.argv) > 2 else None
    success = convert(svoFile, mp4File)
    sys.exit(0 if success else 1)
