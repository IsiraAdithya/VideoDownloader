import os
import subprocess
import signal
import threading
import tkinter as tk
from tkinter import messagebox, ttk
from PIL import Image, ImageTk
import requests
from io import BytesIO
import time
import re
import sys

download_threads = []
download_processes = []


def download_video(url, download_path, progress_var, speed_var, index):
    try:
        # Ensure yt-dlp is installed
        subprocess.run(['pip', 'install', '--upgrade', 'yt-dlp'], check=True)

        # Create download path if it doesn't exist
        if not os.path.exists(download_path):
            os.makedirs(download_path)

        # Run yt-dlp command to download the video with highest quality by default
        command = ['yt-dlp', '-f', 'bestvideo[height<=2160]+bestaudio/best', '--merge-output-format', 'mp4', '-o',
                   os.path.join(download_path, '%(title)s.%(ext)s'), url]
        process = subprocess.Popen(command, stdout=subprocess.PIPE, stderr=subprocess.STDOUT, text=True,
                                   encoding='utf-8', errors='replace')
        download_processes[index] = process

        # Update progress bar and speed
        previous_time = time.time()
        previous_downloaded = 0
        unit_multipliers = {'B': 1, 'K': 1024, 'M': 1024 ** 2, 'G': 1024 ** 3}
        for line in process.stdout:
            if "[download]" in line and ("% of" in line or " at " in line):
                parts = line.split()
                try:
                    percent = float(parts[1].strip('%'))
                except ValueError:
                    continue
                downloaded_str = parts[3].replace('iB', '').replace('B', '')
                match = re.match(r'([0-9.]+)([BKMG])', downloaded_str)
                if match:
                    downloaded = float(match.group(1)) * unit_multipliers[match.group(2)]
                    progress_var[index].set(percent)

                    # Calculate download speed
                    current_time = time.time()
                    elapsed_time = current_time - previous_time
                    if elapsed_time > 0 and downloaded > previous_downloaded:
                        speed = (downloaded - previous_downloaded) / elapsed_time
                        speed_var[index].set(f"{(speed * 8) / 1_000_000:.2f} Mbps")
                        previous_downloaded = downloaded
                        previous_time = current_time

        process.wait()
        if process.returncode == 0:
            progress_var[index].set(100)
            speed_var[index].set('Complete')
            frame = frames[index]

        else:
            speed_var[index].set('Error occurred')
    except subprocess.CalledProcessError as e:
        messagebox.showerror("Error", f"An error occurred: {e}")


def get_video_thumbnail(url):
    try:
        # Get video information and extract thumbnail URL
        result = subprocess.run(['yt-dlp', '--get-thumbnail', url], stdout=subprocess.PIPE, text=True)
        thumbnail_url = result.stdout.strip()
        if thumbnail_url:
            response = requests.get(thumbnail_url)
            img_data = BytesIO(response.content)
            return Image.open(img_data)
    except Exception as e:
        print(f"Error fetching thumbnail: {e}")
    return None


def start_download():
    urls = url_text.get("1.0", tk.END).strip().splitlines()
    download_path = fixed_download_path
    if not urls:
        messagebox.showwarning("Input Error", "Please enter the URLs.")
    else:
        progress_vars.clear()
        speed_vars.clear()
        download_threads.clear()
        download_processes.clear()
        for i, url in enumerate(urls):
            progress_var = tk.DoubleVar()
            speed_var = tk.StringVar()
            progress_vars.append(progress_var)
            speed_vars.append(speed_var)
            download_processes.append(None)

            # Frame for each video download
            frame = tk.Frame(scrollable_frame)
            frame.pack(fill=tk.X, padx=10, pady=5)
            frames.append(frame)

            # Thumbnail with progress bar
            thumbnail_frame = tk.Frame(frame)
            thumbnail_frame.pack(side=tk.LEFT, padx=5)
            thumbnail_progress = ttk.Progressbar(thumbnail_frame, mode='indeterminate', length=100)
            thumbnail_progress.pack()
            thumbnail_progress.start()

            thumbnail = get_video_thumbnail(url)
            thumbnail_progress.stop()
            thumbnail_progress.pack_forget()

            if thumbnail:
                thumbnail = thumbnail.resize((100, 60), Image.LANCZOS)
                thumbnail_image = ImageTk.PhotoImage(thumbnail)
                thumbnail_label = tk.Label(thumbnail_frame, image=thumbnail_image)
                thumbnail_label.image = thumbnail_image
                thumbnail_label.pack()
            else:
                placeholder_label = tk.Label(thumbnail_frame, text="No Thumbnail", width=12, height=5)
                placeholder_label.pack()

            # Progress bar
            progress_bar = ttk.Progressbar(frame, variable=progress_var, maximum=100)
            progress_bar.pack(fill=tk.X, padx=10, pady=5)

            # Download speed and percentage
            speed_label = tk.Label(frame, textvariable=speed_var)
            speed_label.pack(side=tk.RIGHT, padx=5)
            percentage_label = tk.Label(frame, text="0", textvariable=progress_var)
            percentage_label.pack(side=tk.RIGHT, padx=5)

            # Pause and Stop buttons
            pause_button = tk.Button(frame, text="Pause", command=lambda i=i: pause_download(i))
            pause_button.pack(side=tk.LEFT, padx=5)
            resume_button = tk.Button(frame, text="Resume", command=lambda i=i: resume_download(i))
            resume_button.pack(side=tk.LEFT, padx=5)
            stop_button = tk.Button(frame, text="Stop", command=lambda i=i: stop_download(i))
            stop_button.pack(side=tk.LEFT, padx=5)
            remove_button = tk.Button(frame, text="Remove", command=lambda i=i: remove_download(i))
            remove_button.pack(side=tk.LEFT, padx=5)

            thread = threading.Thread(target=download_video, args=(url, download_path, progress_vars, speed_vars, i))
            thread.start()
            download_threads.append(thread)


def pause_download(index):
    if download_processes[index] and download_processes[index].poll() is None:
        download_processes[index].terminate()  # Pause by terminating the current download process


def resume_download(index):
    urls = url_text.get("1.0", tk.END).strip().splitlines()
    if index < len(urls):
        url = urls[index]
        thread = threading.Thread(target=download_video,
                                  args=(url, fixed_download_path, progress_vars, speed_vars, index))
        thread.start()
        download_threads[index] = thread  # Resume by restarting the download


def remove_download(index):
    frame = frames[index]
    frame.pack_forget()


def stop_download(index):
    if download_processes[index] and download_processes[index].poll() is None:
        download_processes[index].terminate()
        download_threads[index].join()
        speed_var[index].set('Stopped')


def paste_url():
    pasted_url = url_entry.get()
    if pasted_url:
        url_text.insert(tk.END, pasted_url + '\n')
        url_entry.delete(0, tk.END)
        paste_window.withdraw()


def open_paste_window():
    global paste_window
    paste_window = tk.Toplevel(root)
    paste_window.title("Paste URL")
    paste_window.geometry("400x100")
    paste_window.attributes('-topmost', True)
    paste_window.after(100, lambda: paste_window.focus_force())

    paste_label = tk.Label(paste_window, text="Paste the URL:")
    paste_label.pack(pady=5)

    global url_entry
    url_entry = tk.Entry(paste_window, width=50)
    url_entry.pack(pady=5)

    paste_button = tk.Button(paste_window, text="Paste and Close", command=paste_url)
    paste_button.pack(pady=5)


# Create GUI
root = tk.Tk()
root.title("Video Downloader")
root.geometry("600x700")

# Add a scrollable frame
main_frame = tk.Frame(root)
main_frame.pack(fill=tk.BOTH, expand=1)
canvas = tk.Canvas(main_frame)
scrollbar = ttk.Scrollbar(main_frame, orient=tk.VERTICAL, command=canvas.yview)
scrollable_frame = tk.Frame(canvas)

scrollable_frame.bind(
    "<Configure>",
    lambda e: canvas.configure(
        scrollregion=canvas.bbox("all")
    )
)

canvas.create_window((0, 0), window=scrollable_frame, anchor="nw")
canvas.configure(yscrollcommand=scrollbar.set)

canvas.pack(side=tk.LEFT, fill=tk.BOTH, expand=1)
scrollbar.pack(side=tk.RIGHT, fill=tk.Y)

# URL Text Entry
url_text = tk.Text(root, width=60, height=5)
url_text.pack(pady=5)

# Fixed Download Path
fixed_download_path = os.path.join(os.getcwd(), "Downloads")
if not os.path.exists(fixed_download_path):
    os.makedirs(fixed_download_path)

# Progress Bar and Speed Variables
progress_vars = []
speed_vars = []
frames = []

# Download Button
download_button = tk.Button(root, text="Download Videos", command=start_download)
download_button.pack(pady=10)

# Paste URL Button
paste_url_button = tk.Button(root, text="Paste URL", command=open_paste_window)
paste_url_button.pack(pady=10)

root.mainloop()