import cv2
import os
import sys
import time
import argparse
import logging
from backend.app.core.config import settings
from backend.app.db.session import init_db, get_security_summary
from backend.app.vision.pipeline import vision_pipeline

logging.basicConfig(level=logging.INFO, format="%(asctime)s [%(levelname)s] %(message)s")
logger = logging.getLogger("security_demo")

def run_security_demo(
    source: str = "0",
    camera_id: str = "cam-01",
    camera_location: str = "Campus Gate 1",
    max_frames: int = 0,
    output_image: str = "latest_frame.jpg"
):
    """
    Demonstration of the Security Module MVP:
    - Compatible with opencv-python-headless (no GUI window required)
    - Captures frames from webcam or video file
    - Runs real-time face detection & 3-way identity (Known, Unknown, Blacklisted)
    - Automatically creates security alerts and logs events to database
    - Saves the annotated frame with bounding boxes to `latest_frame.jpg`
    - Displays real-time terminal telemetry
    """
    print("=" * 68)
    print("   SMART ATTENDANCE & SECURITY SYSTEM - SECURITY MODULE DEMO")
    print("=" * 68)
    print("Initializing database & tables...")
    init_db()

    src = int(source) if source.isdigit() else source
    print(f"Connecting to camera source: {src} (Camera: {camera_id}, Location: {camera_location})")

    cap = cv2.VideoCapture(src)
    if not cap.isOpened():
        print(f"\n[ERROR] Unable to open camera source '{source}'.")
        print("Tip: If you do not have an active webcam, pass a video file: python demo_security.py --source data/demo.mp4")
        sys.exit(1)

    cap.set(cv2.CAP_PROP_FRAME_WIDTH, 640)
    cap.set(cv2.CAP_PROP_FRAME_HEIGHT, 480)

    print("\nSecurity module is LIVE!")
    print("Operating Mode: Headless Surveillance Worker (CPU-optimized)")
    print("Telemetry & alerts are logged to database in real-time.")
    print(f"Annotated frame is continuously updated at '{output_image}'.")
    if max_frames > 0:
        print(f"Running for {max_frames} frames... (or press Ctrl+C to stop earlier)")
    else:
        print("Running continuously... Press Ctrl+C in terminal to stop.")
    print("-" * 68)

    frame_count = 0
    total_detections = 0
    start_time = time.time()

    # Check whether GUI windows are supported by the installed OpenCV build
    has_gui = False
    try:
        cv2.namedWindow("__probe__", cv2.WINDOW_AUTOSIZE)
        cv2.destroyWindow("__probe__")
        has_gui = True
    except (cv2.error, AttributeError):
        has_gui = False

    try:
        while True:
            ret, frame = cap.read()
            if not ret or frame is None:
                if not str(src).isdigit():
                    # Video file rewind
                    cap.set(cv2.CAP_PROP_POS_FRAMES, 0)
                    continue
                else:
                    print("\n[WARN] Failed to grab frame from webcam. Retrying...")
                    time.sleep(0.2)
                    continue

            frame_count += 1

            # Process frame through Vision Pipeline
            annotated_frame, new_alerts = vision_pipeline.process_frame(
                frame=frame,
                camera_id=camera_id,
                camera_location=camera_location
            )

            # Save latest annotated frame for viewing
            cv2.imwrite(output_image, annotated_frame)

            # Check if any faces were detected
            bboxes = vision_pipeline.detector.detect_faces(frame)
            if bboxes:
                total_detections += len(bboxes)
                for alert in new_alerts:
                    print(f"[ALERT GENERATED] {alert['alert_type']} [{alert['severity']}] on {camera_id} for '{alert['person_name']}'")

                print(f"[Frame {frame_count:04d}] {len(bboxes)} face(s) tracked | Output saved -> {output_image}")
            elif frame_count % 30 == 0:
                print(f"[Frame {frame_count:04d}] Scanning feed... No faces in view.")

            # If GUI is available, display window; otherwise do headless sleep
            if has_gui:
                try:
                    cv2.imshow("Security Module Demo", annotated_frame)
                    key = cv2.waitKey(1) & 0xFF
                    if key == ord('q') or key == 27:
                        break
                except cv2.error:
                    has_gui = False
            else:
                time.sleep(0.03)

            if max_frames > 0 and frame_count >= max_frames:
                print(f"\nReached target of {max_frames} frames.")
                break

    except KeyboardInterrupt:
        print("\nKeyboardInterrupt received. Stopping surveillance...")
    finally:
        cap.release()
        if has_gui:
            try:
                cv2.destroyAllWindows()
            except Exception:
                pass

    elapsed = round(time.time() - start_time, 1)
    fps = round(frame_count / elapsed, 1) if elapsed > 0 else 0.0

    print("\n" + "=" * 68)
    print("                    DEMO SESSION SUMMARY")
    print("=" * 68)
    print(f"Frames Processed:        {frame_count} frames ({elapsed}s @ {fps} FPS)")
    print(f"Total Face Sightings:    {total_detections}")
    print(f"Latest Annotated Frame:  {os.path.abspath(output_image)}")
    summary = get_security_summary()
    print(f"Total Active Alerts:     {summary.get('active_alerts', 0)}")
    print(f"Unknown Person Alerts:   {summary.get('unknown_alerts', 0)}")
    print(f"Blacklist Threat Alerts: {summary.get('blacklist_alerts', 0)}")
    print(f"Active Blacklist Count:  {summary.get('active_blacklist_entries', 0)}")
    print("=" * 68)
    print("[SUCCESS] Demo session completed successfully.\n")

if __name__ == "__main__":
    parser = argparse.ArgumentParser(description="Live Security Module Demonstration (Headless & Streamlit compatible)")
    parser.add_argument("--source", type=str, default="0", help="Camera index (e.g. 0 for webcam) or video file path")
    parser.add_argument("--camera-id", type=str, default="cam-01", help="Identifier for this camera feed")
    parser.add_argument("--location", type=str, default="Campus Gate 1", help="Campus location name")
    parser.add_argument("--frames", type=int, default=0, help="Number of frames to process (0 for continuous)")
    parser.add_argument("--output", type=str, default="latest_frame.jpg", help="Path to save latest annotated frame")
    args = parser.parse_args()

    run_security_demo(
        source=args.source,
        camera_id=args.camera_id,
        camera_location=args.location,
        max_frames=args.frames,
        output_image=args.output
    )
