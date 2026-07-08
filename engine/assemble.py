# -*- coding: utf-8 -*-
"""ffmpeg assembly for Family Trailer Studio.

Ports the proven segment builders (Ken Burns, hair->bald reveal, video overlay,
music ducking, concat) from build_trailer3.py into a parametrized Assembler that
consumes rendered scene dicts.
"""
import os
import subprocess
import sys


class Assembler:
    def __init__(self, assets_root, music_dir, sfx_dir, scenes_dir, vo_dir, seg_dir,
                 fps=30, size=(1920, 1080)):
        self.A = _slash(assets_root)
        self.M = _slash(music_dir)
        self.SFX = _slash(sfx_dir)
        self.SC = _slash(scenes_dir)
        self.VO = _slash(vo_dir)
        self.SEG = _slash(seg_dir)
        os.makedirs(self.SEG, exist_ok=True)
        self.FPS = fps
        self.W, self.H = size

    # ---- helpers -----------------------------------------------------------
    def _run(self, args):
        p = subprocess.run(args, stdout=subprocess.PIPE, stderr=subprocess.STDOUT,
                           text=True, encoding="utf-8", errors="replace")
        if p.returncode != 0:
            print(p.stdout[-3500:])
            sys.exit("FFMPEG FAILED")

    def _music(self, name):
        if os.path.isabs(name):
            return name
        cand = self.A + name          # project-relative (e.g. an uploaded uploads/*.mp3)
        if os.path.exists(cand):
            return cand
        return self.M + name          # bare name from the shared music library

    def _sfxp(self, s):
        if not s:
            return None
        if os.path.isabs(s):
            return s
        cand = self.A + s          # work-relative (e.g. a synthesized _build/sfx/*.wav)
        if os.path.exists(cand):
            return cand
        return self.SFX + s        # bare name under the sfx dir

    def _zexpr(self, zin):
        return ("min(max(pzoom,1.0)+0.0009,1.14)" if zin
                else "if(eq(on,0),1.14,max(pzoom-0.0009,1.0))")

    def _audio_chain(self, dur, midx, sidx, vidx, vdly, sdelay=0.0):
        duck = vidx is not None
        mvol = 0.30 if duck else (0.62 if sidx is not None else 0.8)
        parts = [f"[{midx}:a]afade=t=in:st=0:d=0.3,afade=t=out:st={dur-0.5:.3f}:d=0.5,volume={mvol}[mus]"]
        lab = ["[mus]"]
        if sidx is not None:
            sd = int(sdelay * 1000)
            parts.append(f"[{sidx}:a]volume=0.85,adelay={sd}|{sd}[sx]")
            lab.append("[sx]")
        if vidx is not None:
            vd = int(vdly * 1000)
            parts.append(f"[{vidx}:a]volume=2.3,adelay={vd}|{vd}[vo]")
            lab.append("[vo]")
        if len(lab) == 1:
            parts.append(f"{lab[0]}aformat=sample_rates=48000:channel_layouts=stereo[a]")
        else:
            parts.append(f"{''.join(lab)}amix=inputs={len(lab)}:duration=first:normalize=0,"
                         f"alimiter=limit=0.95,aformat=sample_rates=48000:channel_layouts=stereo[a]")
        return ";".join(parts)

    def _enc(self, args, out, dur):
        args += ["-map", "[v]", "-map", "[a]", "-t", f"{dur}", "-r", str(self.FPS),
                 "-c:v", "libx264", "-preset", "medium", "-crf", "19", "-pix_fmt", "yuv420p",
                 "-c:a", "aac", "-b:a", "192k", "-ar", "48000", "-ac", "2", out]
        self._run(args)

    # ---- segment builders --------------------------------------------------
    def seg_image(self, idx, sc, frames):
        out = f"{self.SEG}{idx:02d}.mp4"
        dur = sc["duration"]
        fr = round(dur * self.FPS)
        fo = sc.get("fadeout", 0.45)
        W, H = self.W, self.H
        vf = (f"scale={W}:{H},setsar=1,zoompan=z='{self._zexpr(sc.get('zoom_in', True))}':d={fr}:s={W}x{H}:fps={self.FPS}"
              f":x='iw/2-(iw/zoom/2)':y='ih/2-(ih/zoom/2)',"
              f"fade=t=in:st=0:d=0.4,fade=t=out:st={dur-fo:.3f}:d={fo},format=yuv420p")
        args = ["ffmpeg", "-y", "-loop", "1", "-i", frames["frame"],
                "-ss", str(sc.get("music_offset", 0)), "-t", f"{dur}", "-i", self._music(sc["music"])]
        ai = 2
        sidx = vidx = None
        sp = self._sfxp(sc.get("sfx"))
        if sp:
            args += ["-i", sp]; sidx = ai; ai += 1
        vo = sc.get("_vo")
        if vo:
            args += ["-i", vo]; vidx = ai; ai += 1
        fc = f"[0:v]{vf}[v];" + self._audio_chain(dur, 1, sidx, vidx, sc.get("narration_delay", 0.3))
        args += ["-filter_complex", fc]
        self._enc(args, out, dur)
        return out

    def seg_reveal(self, idx, sc, frames):
        out = f"{self.SEG}{idx:02d}.mp4"
        dur = sc["duration"]
        hold = sc.get("hold", 1.7)
        xf = sc.get("xf", 0.7)
        trans = sc.get("transition", "fadewhite")
        W, H = self.W, self.H
        Tb = hold + xf + 0.15
        Ta = dur - hold
        z = "min(max(pzoom,1.0)+0.0006,1.08)"
        args = ["ffmpeg", "-y", "-loop", "1", "-t", f"{Tb}", "-i", frames["before"],
                "-loop", "1", "-t", f"{Ta}", "-i", frames["after"],
                "-ss", str(sc.get("music_offset", 0)), "-t", f"{dur}", "-i", self._music(sc["music"])]
        ai = 3
        sidx = vidx = None
        sp = self._sfxp(sc.get("sfx"))
        if sp:
            args += ["-i", sp]; sidx = ai; ai += 1
        vo = sc.get("_vo")
        if vo:
            args += ["-i", vo]; vidx = ai; ai += 1
        vf = (f"[0:v]scale={W}:{H},setsar=1,zoompan=z='{z}':d={round(Tb*self.FPS)}:s={W}x{H}:fps={self.FPS}:x='iw/2-(iw/zoom/2)':y='ih/2-(ih/zoom/2)'[b];"
              f"[1:v]scale={W}:{H},setsar=1,zoompan=z='{z}':d={round(Ta*self.FPS)}:s={W}x{H}:fps={self.FPS}:x='iw/2-(iw/zoom/2)':y='ih/2-(ih/zoom/2)'[a];"
              f"[b][a]xfade=transition={trans}:duration={xf}:offset={hold},"
              f"fade=t=in:st=0:d=0.4,fade=t=out:st={dur-0.45:.3f}:d=0.45,format=yuv420p[v]")
        fc = vf + ";" + self._audio_chain(dur, 2, sidx, vidx, sc.get("narration_delay", 0.3), sdelay=hold)
        args += ["-filter_complex", fc]
        self._enc(args, out, dur)
        return out

    def _has_audio(self, path):
        p = subprocess.run(["ffprobe", "-v", "error", "-select_streams", "a",
                            "-show_entries", "stream=index", "-of", "csv=p=0", path],
                           stdout=subprocess.PIPE, stderr=subprocess.STDOUT,
                           text=True, encoding="utf-8", errors="replace")
        return bool(p.stdout.strip())

    def seg_video(self, idx, sc, frames):
        out = f"{self.SEG}{idx:02d}.mp4"
        dur = sc.get("duration", 8.0)
        W, H = self.W, self.H
        video = sc["video"] if os.path.isabs(sc["video"]) else self.A + sc["video"]
        cap = frames.get("overlay")
        args = ["ffmpeg", "-y", "-i", video]
        ai = 1
        cap_idx = None
        if cap:
            args += ["-i", cap]; cap_idx = ai; ai += 1
        if self._has_audio(video):
            asrc = "[0:a]"
        else:  # phone clips are often silent — synthesize silence so the render doesn't crash
            args += ["-f", "lavfi", "-t", f"{dur}", "-i", "anullsrc=r=48000:cl=stereo"]
            asrc = f"[{ai}:a]"; ai += 1
        vf = ("[0:v]split=2[bg][fg];"
              f"[bg]scale={W}:{H}:force_original_aspect_ratio=increase,crop={W}:{H},boxblur=28:2,eq=brightness=-0.4[bgb];"
              f"[fg]scale={W}:{H}:force_original_aspect_ratio=decrease[fgs];"
              "[bgb][fgs]overlay=(W-w)/2:(H-h)/2[comp];")
        vf += f"[comp][{cap_idx}:v]overlay=0:0,setsar=1," if cap else "[comp]setsar=1,"
        vf += (f"fade=t=in:st=0:d=0.4,fade=t=out:st={dur-0.5:.3f}:d=0.5,format=yuv420p[v];"
               f"{asrc}afade=t=in:st=0:d=0.2,afade=t=out:st={dur-0.5:.3f}:d=0.5,volume=0.9,"
               "aformat=sample_rates=48000:channel_layouts=stereo[a]")
        args += ["-filter_complex", vf]
        self._enc(args, out, dur)
        return out

    # ---- top-level ---------------------------------------------------------
    def build(self, scenes, out_path):
        segs = []
        for i, sc in enumerate(scenes, start=1):
            frames = sc["_frames"]
            t = sc["type"]
            if t == "reveal":
                segs.append(self.seg_reveal(i, sc, frames))
            elif t == "video":
                segs.append(self.seg_video(i, sc, frames))
            else:
                segs.append(self.seg_image(i, sc, frames))
            print("seg", i, sc["id"])
        lst = self.SEG + "list.txt"
        with open(lst, "w", encoding="utf-8") as fh:
            for s in segs:
                fh.write(f"file '{os.path.abspath(s)}'\n")
        os.makedirs(os.path.dirname(out_path), exist_ok=True)
        self._run(["ffmpeg", "-y", "-f", "concat", "-safe", "0", "-i", lst, "-c", "copy", out_path])
        return out_path


def _slash(p):
    return p.replace("\\", "/").rstrip("/") + "/"
