#!/usr/bin/env python3
"""
مسجل المحاضرات مع واتساب
Lecture Recorder with WhatsApp Integration
"""

import tkinter as tk
from tkinter import ttk, messagebox, filedialog
import threading
import pyaudio
import wave
import speech_recognition as sr
import pywhatkit
import os
import tempfile
import time


# ─── Audio Recorder ────────────────────────────────────────────────────────────

class AudioRecorder:
    FORMAT = pyaudio.paInt16
    CHANNELS = 1
    RATE = 44100
    CHUNK = 1024

    def __init__(self):
        self.audio = pyaudio.PyAudio()
        self.stream = None
        self.all_frames = []
        self.is_paused = False

    def start(self):
        self.all_frames = []
        self.is_paused = False
        self.stream = self.audio.open(
            format=self.FORMAT,
            channels=self.CHANNELS,
            rate=self.RATE,
            input=True,
            frames_per_buffer=self.CHUNK,
        )

    def read_chunk(self):
        if self.stream and not self.is_paused:
            data = self.stream.read(self.CHUNK, exception_on_overflow=False)
            self.all_frames.append(data)
            return data
        return None

    def pause(self):
        self.is_paused = True

    def resume(self):
        self.is_paused = False

    def stop(self):
        if self.stream:
            self.stream.stop_stream()
            self.stream.close()
            self.stream = None

    def save_frames(self, frames, path):
        with wave.open(path, "wb") as wf:
            wf.setnchannels(self.CHANNELS)
            wf.setsampwidth(self.audio.get_sample_size(self.FORMAT))
            wf.setframerate(self.RATE)
            wf.writeframes(b"".join(frames))

    def save_full_recording(self, path):
        self.save_frames(self.all_frames, path)

    def cleanup(self):
        self.audio.terminate()


# ─── Main Application ──────────────────────────────────────────────────────────

class LectureRecorderApp:
    # Catppuccin Mocha palette
    C = {
        "bg":        "#1e1e2e",
        "surface":   "#313244",
        "overlay":   "#45475a",
        "text":      "#cdd6f4",
        "subtext":   "#a6adc8",
        "blue":      "#89b4fa",
        "lavender":  "#b4befe",
        "mauve":     "#cba6f7",
        "green":     "#a6e3a1",
        "red":       "#f38ba8",
        "peach":     "#fab387",
        "teal":      "#94e2d5",
        "whatsapp":  "#25D366",
    }

    # Frames collected per transcription segment (default 15 s)
    SEGMENT_SECONDS = 15

    def __init__(self, root: tk.Tk):
        self.root = root
        self.root.title("مسجل المحاضرات | Lecture Recorder")
        self.root.geometry("960x720")
        self.root.minsize(800, 600)
        self.root.configure(bg=self.C["bg"])

        self.recorder = AudioRecorder()
        self.recognizer = sr.Recognizer()

        self.is_recording = False
        self.is_paused = False
        self.record_thread = None

        # Timer state
        self.elapsed_seconds = 0
        self.last_tick = 0.0
        self._timer_id = None

        # REC blink state
        self._blink_id = None
        self._blink_on = True

        self.language = tk.StringVar(value="ar-SA")

        self._build_ui()

    # ── UI ──────────────────────────────────────────────────────────────────

    def _build_ui(self):
        root = self.root
        C = self.C

        pad = dict(padx=16, pady=8)

        # ── Header ──
        hdr = tk.Frame(root, bg=C["bg"])
        hdr.pack(fill=tk.X, padx=20, pady=(18, 0))

        tk.Label(hdr, text="🎙  مسجل المحاضرات",
                 bg=C["bg"], fg=C["blue"],
                 font=("Segoe UI", 20, "bold")).pack(side=tk.LEFT)
        tk.Label(hdr, text="Lecture Recorder",
                 bg=C["bg"], fg=C["mauve"],
                 font=("Segoe UI", 14)).pack(side=tk.RIGHT, pady=6)

        tk.Frame(root, bg=C["overlay"], height=1).pack(fill=tk.X, padx=20, pady=8)

        # ── Controls row ──
        ctrl = tk.Frame(root, bg=C["surface"], pady=12)
        ctrl.pack(fill=tk.X, padx=20, pady=(0, 12))

        # Timer + REC indicator
        timer_box = tk.Frame(ctrl, bg=C["surface"])
        timer_box.pack(side=tk.LEFT, padx=(16, 24))

        self.timer_lbl = tk.Label(timer_box, text="00:00:00",
                                  bg=C["surface"], fg=C["peach"],
                                  font=("Courier New", 18, "bold"))
        self.timer_lbl.pack()

        self.rec_lbl = tk.Label(timer_box, text="● REC",
                                bg=C["surface"], fg=C["surface"],  # hidden initially
                                font=("Segoe UI", 9, "bold"))
        self.rec_lbl.pack()

        # Buttons
        btn_box = tk.Frame(ctrl, bg=C["surface"])
        btn_box.pack(side=tk.LEFT, fill=tk.X, expand=True)

        self.record_btn = self._btn(btn_box, "⏺  تسجيل / Record",
                                    C["green"], "#1e1e2e", self.start_recording,
                                    font_size=11)
        self.record_btn.pack(side=tk.LEFT, padx=6)

        self.pause_btn = self._btn(btn_box, "⏸  إيقاف مؤقت",
                                   C["overlay"], C["text"], self.toggle_pause)
        self.pause_btn.pack(side=tk.LEFT, padx=4)
        self.pause_btn["state"] = tk.DISABLED

        self.stop_btn = self._btn(btn_box, "⏹  إيقاف / Stop",
                                  C["red"], "#1e1e2e", self.stop_recording,
                                  font_size=10)
        self.stop_btn.pack(side=tk.LEFT, padx=4)
        self.stop_btn["state"] = tk.DISABLED

        # Language + save recording
        right_box = tk.Frame(ctrl, bg=C["surface"])
        right_box.pack(side=tk.RIGHT, padx=16)

        tk.Label(right_box, text="اللغة / Language",
                 bg=C["surface"], fg=C["subtext"], font=("Segoe UI", 8)).pack(anchor=tk.W)

        lang_cb = ttk.Combobox(right_box, textvariable=self.language, width=14,
                               values=["ar-SA", "ar-EG", "ar-AE",
                                       "en-US", "en-GB", "fr-FR", "de-DE"],
                               state="readonly", font=("Segoe UI", 10))
        lang_cb.pack(pady=(2, 6))

        self._btn(right_box, "💾  حفظ التسجيل",
                  C["overlay"], C["teal"], self.save_recording,
                  font_size=9).pack(fill=tk.X)

        # ── Transcription area ──
        lbl_row = tk.Frame(root, bg=C["bg"])
        lbl_row.pack(fill=tk.X, padx=20, pady=(0, 4))

        tk.Label(lbl_row, text="📝  النص المُفرَّغ / Transcription",
                 bg=C["bg"], fg=C["lavender"],
                 font=("Segoe UI", 11, "bold")).pack(side=tk.LEFT)

        btn_row = tk.Frame(lbl_row, bg=C["bg"])
        btn_row.pack(side=tk.RIGHT)

        for label, cmd in [("نسخ الكل", self.copy_all),
                            ("نسخ المحدد", self.copy_selection),
                            ("مسح / Clear", self.clear_text)]:
            self._btn(btn_row, label, C["overlay"], C["text"], cmd,
                      font_size=9, pad_x=10, pad_y=3).pack(side=tk.LEFT, padx=3)

        txt_outer = tk.Frame(root, bg=C["blue"], padx=1, pady=1)
        txt_outer.pack(fill=tk.BOTH, expand=True, padx=20, pady=(0, 12))

        txt_inner = tk.Frame(txt_outer, bg=C["surface"])
        txt_inner.pack(fill=tk.BOTH, expand=True)

        self.text_area = tk.Text(
            txt_inner, wrap=tk.WORD,
            bg=C["surface"], fg=C["text"],
            font=("Segoe UI", 13), padx=12, pady=10,
            relief=tk.FLAT, insertbackground=C["blue"],
            selectbackground=C["blue"], selectforeground="#1e1e2e",
        )
        vsb = ttk.Scrollbar(txt_inner, orient=tk.VERTICAL,
                            command=self.text_area.yview)
        self.text_area.configure(yscrollcommand=vsb.set)
        vsb.pack(side=tk.RIGHT, fill=tk.Y)
        self.text_area.pack(fill=tk.BOTH, expand=True)

        # ── WhatsApp panel ──
        wa_outer = tk.Frame(root, bg=C["whatsapp"], padx=2, pady=2)
        wa_outer.pack(fill=tk.X, padx=20, pady=(0, 10))

        wa = tk.Frame(wa_outer, bg=C["surface"], padx=14, pady=10)
        wa.pack(fill=tk.X)

        tk.Label(wa, text="📱  إرسال عبر واتساب / Send via WhatsApp",
                 bg=C["surface"], fg=C["whatsapp"],
                 font=("Segoe UI", 11, "bold")).pack(anchor=tk.W, pady=(0, 8))

        row1 = tk.Frame(wa, bg=C["surface"])
        row1.pack(fill=tk.X)

        tk.Label(row1, text="رقم الهاتف / Phone Number:",
                 bg=C["surface"], fg=C["subtext"],
                 font=("Segoe UI", 10)).pack(side=tk.LEFT, padx=(0, 8))

        self.phone_var = tk.StringVar()
        phone_entry = tk.Entry(
            row1, textvariable=self.phone_var, width=22,
            bg=C["overlay"], fg=C["text"],
            font=("Segoe UI", 11), relief=tk.FLAT,
            insertbackground=C["blue"],
        )
        phone_entry.pack(side=tk.LEFT, ipady=5, ipadx=6, padx=(0, 6))

        tk.Label(row1, text="مثال / e.g.: +966501234567",
                 bg=C["surface"], fg=C["overlay"],
                 font=("Segoe UI", 8)).pack(side=tk.LEFT, padx=(0, 20))

        self.send_selection = tk.BooleanVar(value=False)
        tk.Checkbutton(
            row1, text="إرسال المحدد فقط / Selection only",
            variable=self.send_selection,
            bg=C["surface"], fg=C["subtext"],
            selectcolor=C["overlay"],
            activebackground=C["surface"],
            activeforeground=C["text"],
            font=("Segoe UI", 9),
        ).pack(side=tk.LEFT, padx=(0, 20))

        self.send_btn = self._btn(row1, "إرسال  ➤",
                                  C["whatsapp"], "white",
                                  self.send_whatsapp,
                                  font_size=11, pad_x=22, pad_y=6)
        self.send_btn.pack(side=tk.LEFT)

        # ── Status bar ──
        self.status_var = tk.StringVar(value="  جاهز / Ready")
        tk.Label(root, textvariable=self.status_var,
                 bg=C["overlay"], fg=C["subtext"],
                 font=("Segoe UI", 9), anchor=tk.W,
                 padx=12, pady=4).pack(fill=tk.X, side=tk.BOTTOM)

    def _btn(self, parent, text, bg, fg, cmd,
             font_size=10, pad_x=14, pad_y=6):
        return tk.Button(
            parent, text=text, command=cmd,
            bg=bg, fg=fg, activebackground=bg, activeforeground=fg,
            font=("Segoe UI", font_size, "bold"),
            padx=pad_x, pady=pad_y, relief=tk.FLAT, cursor="hand2",
        )

    # ── Recording ──────────────────────────────────────────────────────────

    def start_recording(self):
        self.is_recording = True
        self.is_paused = False
        self.elapsed_seconds = 0
        self.last_tick = time.time()

        self.recorder.start()

        self.record_btn["state"] = tk.DISABLED
        self.record_btn["text"] = "⏺  جارٍ التسجيل..."
        self.record_btn["bg"] = self.C["red"]
        self.pause_btn["state"] = tk.NORMAL
        self.stop_btn["state"] = tk.NORMAL

        self._start_timer()
        self._start_blink()

        self.record_thread = threading.Thread(
            target=self._record_loop, daemon=True)
        self.record_thread.start()

        self._set_status("جارٍ التسجيل... / Recording in progress…")

    def _record_loop(self):
        segment: list[bytes] = []
        frames_per_seg = int(
            AudioRecorder.RATE / AudioRecorder.CHUNK * self.SEGMENT_SECONDS)
        count = 0

        while self.is_recording:
            chunk = self.recorder.read_chunk()
            if chunk:
                segment.append(chunk)
                count += 1
                if count >= frames_per_seg:
                    self._transcribe(list(segment))
                    segment.clear()
                    count = 0
            else:
                time.sleep(0.05)

        if segment:
            self._transcribe(segment)

    def _transcribe(self, frames: list[bytes]):
        tmp_path = ""
        try:
            with tempfile.NamedTemporaryFile(suffix=".wav", delete=False) as f:
                tmp_path = f.name
            self.recorder.save_frames(frames, tmp_path)

            with sr.AudioFile(tmp_path) as src:
                audio = self.recognizer.record(src)
            text = self.recognizer.recognize_google(
                audio, language=self.language.get())

            if text.strip():
                self.root.after(0, self._append_text, text.strip() + " ")
                self.root.after(0, self._set_status,
                                f"✔ {text[:60]}…" if len(text) > 60 else f"✔ {text}")
        except sr.UnknownValueError:
            pass
        except sr.RequestError as e:
            self.root.after(0, self._set_status,
                            f"⚠ خطأ في الاتصال / Connection error: {e}")
        except Exception as e:
            self.root.after(0, self._set_status, f"⚠ {e}")
        finally:
            if tmp_path:
                try:
                    os.unlink(tmp_path)
                except OSError:
                    pass

    def toggle_pause(self):
        if not self.is_paused:
            self.is_paused = True
            self.recorder.pause()
            self.pause_btn["text"] = "▶  استئناف / Resume"
            self.pause_btn["bg"] = self.C["green"]
            self.rec_lbl["fg"] = self.C["surface"]
            if self._blink_id:
                self.root.after_cancel(self._blink_id)
                self._blink_id = None
            self._set_status("متوقف مؤقتاً / Paused")
        else:
            self.is_paused = False
            self.last_tick = time.time()
            self.recorder.resume()
            self.pause_btn["text"] = "⏸  إيقاف مؤقت"
            self.pause_btn["bg"] = self.C["overlay"]
            self._start_blink()
            self._set_status("جارٍ التسجيل... / Recording in progress…")

    def stop_recording(self):
        self.is_recording = False
        self.is_paused = False
        self.recorder.stop()

        if self._timer_id:
            self.root.after_cancel(self._timer_id)
            self._timer_id = None
        if self._blink_id:
            self.root.after_cancel(self._blink_id)
            self._blink_id = None

        self.rec_lbl["fg"] = self.C["surface"]
        self.record_btn["state"] = tk.NORMAL
        self.record_btn["text"] = "⏺  تسجيل / Record"
        self.record_btn["bg"] = self.C["green"]
        self.pause_btn["state"] = tk.DISABLED
        self.pause_btn["text"] = "⏸  إيقاف مؤقت"
        self.pause_btn["bg"] = self.C["overlay"]
        self.stop_btn["state"] = tk.DISABLED

        self._set_status("انتهى التسجيل / Recording stopped")

    def save_recording(self):
        if not self.recorder.all_frames:
            messagebox.showinfo("تنبيه", "لا يوجد تسجيل للحفظ / No recording to save")
            return
        path = filedialog.asksaveasfilename(
            defaultextension=".wav",
            filetypes=[("WAV Audio", "*.wav"), ("All Files", "*.*")],
            title="حفظ التسجيل / Save Recording",
        )
        if path:
            self.recorder.save_full_recording(path)
            self._set_status(f"✔ تم الحفظ / Saved: {os.path.basename(path)}")

    # ── Timer ──────────────────────────────────────────────────────────────

    def _start_timer(self):
        self._tick_timer()

    def _tick_timer(self):
        if self.is_recording and not self.is_paused:
            now = time.time()
            self.elapsed_seconds += int(now - self.last_tick)
            self.last_tick = now
            h = self.elapsed_seconds // 3600
            m = (self.elapsed_seconds % 3600) // 60
            s = self.elapsed_seconds % 60
            self.timer_lbl["text"] = f"{h:02d}:{m:02d}:{s:02d}"
        if self.is_recording:
            self._timer_id = self.root.after(1000, self._tick_timer)

    # ── REC blink ──────────────────────────────────────────────────────────

    def _start_blink(self):
        self._do_blink()

    def _do_blink(self):
        if not self.is_recording or self.is_paused:
            return
        color = self.C["red"] if self._blink_on else self.C["surface"]
        self.rec_lbl["fg"] = color
        self._blink_on = not self._blink_on
        self._blink_id = self.root.after(600, self._do_blink)

    # ── Text helpers ───────────────────────────────────────────────────────

    def _append_text(self, text: str):
        self.text_area.insert(tk.END, text)
        self.text_area.see(tk.END)

    def copy_all(self):
        text = self.text_area.get("1.0", tk.END).strip()
        if text:
            self.root.clipboard_clear()
            self.root.clipboard_append(text)
            self._set_status("✔ تم نسخ الكل / All text copied")

    def copy_selection(self):
        try:
            text = self.text_area.get(tk.SEL_FIRST, tk.SEL_LAST)
            self.root.clipboard_clear()
            self.root.clipboard_append(text)
            self._set_status("✔ تم نسخ المحدد / Selection copied")
        except tk.TclError:
            self._set_status("⚠ لا يوجد نص محدد / No text selected")

    def clear_text(self):
        self.text_area.delete("1.0", tk.END)
        self._set_status("تم المسح / Cleared")

    # ── WhatsApp ───────────────────────────────────────────────────────────

    def send_whatsapp(self):
        phone = self.phone_var.get().strip().replace(" ", "").replace("-", "")
        if not phone:
            messagebox.showwarning("تحذير",
                                   "الرجاء إدخال رقم الهاتف\nPlease enter a phone number")
            return
        if not phone.startswith("+"):
            phone = "+" + phone

        # Choose text
        if self.send_selection.get():
            try:
                text = self.text_area.get(tk.SEL_FIRST, tk.SEL_LAST).strip()
            except tk.TclError:
                messagebox.showwarning("تحذير",
                                       "الرجاء تحديد النص أولاً\nPlease select text first")
                return
        else:
            text = self.text_area.get("1.0", tk.END).strip()

        if not text:
            messagebox.showwarning("تحذير",
                                   "لا يوجد نص للإرسال\nNo text to send")
            return

        self.send_btn["state"] = tk.DISABLED
        self._set_status("⏳ جارٍ الفتح في واتساب ويب... / Opening WhatsApp Web…")

        def _do_send():
            try:
                pywhatkit.sendwhatmsg_instantly(
                    phone, text, wait_time=12, tab_close=True, close_time=4
                )
                self.root.after(0, self._set_status,
                                "✔ تم الإرسال بنجاح / Sent successfully!")
            except Exception as exc:
                self.root.after(0, self._set_status, f"⚠ خطأ / Error: {exc}")
                self.root.after(0, messagebox.showerror,
                                "خطأ في الإرسال / Send Error", str(exc))
            finally:
                self.root.after(0, lambda: self.send_btn.config(state=tk.NORMAL))

        threading.Thread(target=_do_send, daemon=True).start()

    # ── Status ─────────────────────────────────────────────────────────────

    def _set_status(self, msg: str):
        self.status_var.set(f"  {msg}")

    # ── Cleanup ────────────────────────────────────────────────────────────

    def on_close(self):
        if self.is_recording:
            self.stop_recording()
        self.recorder.cleanup()
        self.root.destroy()


# ─── Entry point ───────────────────────────────────────────────────────────────

def main():
    root = tk.Tk()
    app = LectureRecorderApp(root)
    root.protocol("WM_DELETE_WINDOW", app.on_close)
    root.mainloop()


if __name__ == "__main__":
    main()
