import sys
import argparse
import ui.boat_desktop 

def main():
    parser = argparse.ArgumentParser(description="海況判定アプリ起動ツール")
    parser.add_argument("--mode", choices=["desktop", "web"], default="desktop", help="起動するUIを選択します")
    args = parser.parse_args()

    if args.mode == "desktop":
        print("デスクトップ版を起動します...")
        # ここで名前が一致していることが重要です
        ui.boat_desktop.run_boat_desktop()
        
    elif args.mode == "web":
        print("Web版（Streamlit）を起動します...")
        import subprocess
        subprocess.run([sys.executable, "-m", "streamlit", "run", "ui/boat_web.py"])

if __name__ == "__main__":
    main()
