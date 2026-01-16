import json
import os
import argparse
import time
from datetime import datetime

def generate_data_row(file_idx, row_idx):
    return {
        "colA": f"sample_{file_idx}_{row_idx}_{datetime.now().strftime('%H%M%S')}",
        "colB": file_idx * 1000 + row_idx,
        "colC": float(file_idx * 100 + row_idx * 0.5)
    }

def generate_input_files(directory="./input_data/", num_files=2, lines_per_file=5, mode="batch", rate=1.0, duration=None):
    if not os.path.exists(directory):
        os.makedirs(directory)
        print(f"Created directory: {directory}")

    start_time = time.time()

    if mode == "batch":
        print(f"Running in BATCH mode: generating {num_files} files with {lines_per_file} lines each.")
        for i in range(num_files):
            # Check duration for batch if specified
            if duration and (time.time() - start_time) > duration:
                print(f"Reached duration limit of {duration}s. Stopping batch generation.")
                break
            
            file_path = os.path.join(directory, f"input_batch_{i}.json")
            with open(file_path, "w") as f:
                for j in range(lines_per_file):
                    data = generate_data_row(i, j)
                    f.write(json.dumps(data) + "\n")
            print(f"Generated {file_path}")
    else:
        print(f"Running in STREAMING mode: generating data at {rate} rows/sec.")
        if duration:
            print(f"Will run for {duration} seconds.")
        print("Press Ctrl+C to stop.")
        
        try:
            file_idx = 0
            row_idx = 0
            while True:
                current_time = time.time()
                elapsed = current_time - start_time
                
                if duration and elapsed > duration:
                    print(f"\nReached duration limit of {duration}s. Stopping stream.")
                    break
                
                file_path = os.path.join(directory, f"stream_{int(time.time() * 1000)}.json")
                with open(file_path, "w") as f:
                    data = generate_data_row(file_idx, row_idx)
                    f.write(json.dumps(data) + "\n")
                
                print(f"[{datetime.now().strftime('%Y-%m-%d %H:%M:%S')}] Generated {file_path}: {data}")
                
                row_idx += 1
                if row_idx % 100 == 0:
                    file_idx += 1
                
                # Calculate sleep to maintain rate
                time.sleep(1.0 / rate)
        except KeyboardInterrupt:
            print("\nStreaming stopped by user.")

if __name__ == "__main__":
    parser = argparse.ArgumentParser(description="Generate input files for Pathway pipeline.")
    parser.add_argument("--dir", type=str, default="./input_data/", help="Output directory")
    parser.add_argument("--mode", type=str, choices=["batch", "stream"], default="batch", help="Execution mode")
    parser.add_argument("--rate", type=float, default=1.0, help="Rows per second (only for stream mode)")
    parser.add_argument("--duration", type=float, default=None, help="Duration to run in seconds")
    parser.add_argument("--files", type=int, default=2, help="Number of files (only for batch mode)")
    parser.add_argument("--lines", type=int, default=5, help="Lines per file (only for batch mode)")
    
    args = parser.parse_args()
    generate_input_files(
        directory=args.dir, 
        num_files=args.files, 
        lines_per_file=args.lines, 
        mode=args.mode, 
        rate=args.rate,
        duration=args.duration
    )
