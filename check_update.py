"""
예배 출석 관리 앱
필수 설치: pip install tkcalendar
"""
import tkinter as tk
from tkinter import ttk, messagebox
import json, os, time
from datetime import date

try:
    from tkcalendar import Calendar
    HAS_CAL = True
except ImportError:
    HAS_CAL = False

# ── 데이터 ───────────────────────────────────────────────────────
DATA_FILE = "worship_data.json"

POSITIONS = ["선택 안 함", "4번 카메라", "5번 카메라", "6번 카메라", "7번 카메라", "PD", "TD",
             "노출", "자막", "LED", "조명", "사진 촬영", "릴스", "FD", "음향"]

def load_data():
    if os.path.exists(DATA_FILE):
        with open(DATA_FILE, "r", encoding="utf-8") as f:
            return json.load(f)
    return {"members": [], "attendance": {}}

def save_data(data):
    with open(DATA_FILE, "w", encoding="utf-8") as f:
        json.dump(data, f, ensure_ascii=False, indent=2)

# ── 달력 팝업 ────────────────────────────────────────────────────
class CalendarPopup(tk.Toplevel):
    def __init__(self, parent, date_var, callback):
        super().__init__(parent)
        self.title("날짜 선택")
        self.resizable(False, False)
        self.configure(bg="#F8F7F4")
        self.grab_set()

        try:
            y, m, d = map(int, date_var.get().split("-"))
        except Exception:
            today = date.today()
            y, m, d = today.year, today.month, today.day

        if HAS_CAL:
            cal = Calendar(self, selectmode="day", year=y, month=m, day=d,
                           locale="ko_KR",
                           background="#5038B0", foreground="white",
                           headersbackground="#3C2890", headersforeground="white",
                           selectbackground="#EF9F27", selectforeground="white",
                           normalbackground="#F8F7F4", normalforeground="#222",
                           weekendbackground="#F3F1FB", weekendforeground="#5038B0",
                           font=("맑은 고딕", 10))
            cal.pack(padx=12, pady=12)

            tk.Button(self, text="확인", font=("맑은 고딕", 10, "bold"),
                      bg="#5038B0", fg="white", relief="flat",
                      padx=20, pady=5, cursor="hand2",
                      command=lambda: self._pick(cal.get_date(), date_var, callback)
                      ).pack(pady=(0, 12))
        else:
            tk.Label(self, text="tkcalendar가 설치되지 않았습니다.\n\n  pip install tkcalendar  \n\n설치 후 재시작해 주세요.",
                     font=("맑은 고딕", 11), bg="#F8F7F4", fg="#A32D2D",
                     justify="center").pack(padx=24, pady=24)
            tk.Button(self, text="닫기", font=("맑은 고딕", 10),
                      bg="#DDDAF4", fg="#5038B0", relief="flat",
                      padx=16, pady=4, cursor="hand2",
                      command=self.destroy).pack(pady=(0, 12))

    def _pick(self, date_str, date_var, callback):
        # tkcalendar 반환 형식 MM/DD/YY → YYYY-MM-DD 변환
        try:
            parts = date_str.split("/")
            if len(parts) == 3:
                m, d, y = parts
                y = int(y)
                if y < 100:
                    y += 2000
                formatted = f"{y}-{int(m):02d}-{int(d):02d}"
            else:
                formatted = date_str
        except Exception:
            formatted = date_str
        date_var.set(formatted)
        self.destroy()
        callback()

# ── 멤버 추가/수정 다이얼로그 ────────────────────────────────────
class MemberDialog(tk.Toplevel):
    def __init__(self, parent, on_save, member=None):
        super().__init__(parent)
        self.title("예배자 수정" if member else "예배자 추가")
        self.resizable(False, False)
        self.configure(bg="#F8F7F4")
        self.grab_set()
        self.on_save = on_save
        self.member = member

        pad = dict(padx=16, pady=6)

        # 이름
        tk.Label(self, text="이름 *", font=("맑은 고딕", 10, "bold"),
                 bg="#F8F7F4", fg="#333", anchor="w").pack(fill="x", padx=16, pady=(16, 0))
        self.name_var = tk.StringVar(value=member["name"] if member else "")
        tk.Entry(self, textvariable=self.name_var, font=("맑은 고딕", 11),
                 relief="solid", bd=1, width=26).pack(fill="x", **pad, ipady=4)

        # 포지션
        tk.Label(self, text="포지션", font=("맑은 고딕", 10, "bold"),
                 bg="#F8F7F4", fg="#333", anchor="w").pack(fill="x", padx=16, pady=(4, 0))
        self.pos_var = tk.StringVar(value=member.get("position", "선택 안 함") if member else "선택 안 함")
        pos_cb = ttk.Combobox(self, textvariable=self.pos_var,
                               values=POSITIONS, state="readonly",
                               font=("맑은 고딕", 11), width=24)
        pos_cb.pack(fill="x", **pad, ipady=2)

        # 식사 신청
        tk.Label(self, text="식사 신청", font=("맑은 고딕", 10, "bold"),
                 bg="#F8F7F4", fg="#333", anchor="w").pack(fill="x", padx=16, pady=(4, 0))
        self.meal_var = tk.BooleanVar(value=member.get("meal", False) if member else False)
        meal_frame = tk.Frame(self, bg="#F8F7F4")
        meal_frame.pack(fill="x", padx=16, pady=4)
        tk.Checkbutton(meal_frame, text="식사 신청함",
                       variable=self.meal_var,
                       font=("맑은 고딕", 10),
                       bg="#F8F7F4", fg="#333",
                       activebackground="#F8F7F4",
                       selectcolor="#DDDAF4",
                       cursor="hand2").pack(side="left")

        # 버튼
        btn_row = tk.Frame(self, bg="#F8F7F4")
        btn_row.pack(fill="x", padx=16, pady=(8, 16))
        tk.Button(btn_row, text="취소", font=("맑은 고딕", 10),
                  bg="#EEEEEE", fg="#555", relief="flat",
                  padx=16, pady=5, cursor="hand2",
                  command=self.destroy).pack(side="right", padx=(4, 0))
        tk.Button(btn_row, text="저장", font=("맑은 고딕", 10, "bold"),
                  bg="#5038B0", fg="white", relief="flat",
                  padx=16, pady=5, cursor="hand2",
                  command=self._save).pack(side="right")

    def _save(self):
        name = self.name_var.get().strip()
        if not name:
            messagebox.showwarning("입력 오류", "이름을 입력해 주세요.", parent=self)
            return
        pos = self.pos_var.get()
        meal = self.meal_var.get()
        self.on_save(name, pos, meal)
        self.destroy()

# ── 메인 앱 ──────────────────────────────────────────────────────
class WorshipApp(tk.Tk):
    def __init__(self):
        super().__init__()
        self.title("예배 출석 관리")
        self.geometry("780x660")
        self.minsize(640, 520)
        self.configure(bg="#F8F7F4")
        self.data = load_data()
        self._build_ui()
        self.show_tab("members")

    # ── UI 골격 ──────────────────────────────────────────────────
    def _build_ui(self):
        header = tk.Frame(self, bg="#5038B0", pady=14)
        header.pack(fill="x")
        tk.Label(header, text="⛪  예배 출석 관리",
                 font=("맑은 고딕", 16, "bold"),
                 bg="#5038B0", fg="white").pack()
        tk.Label(header, text="예배자를 등록하고 날짜별 출석 현황을 기록하세요",
                 font=("맑은 고딕", 9), bg="#5038B0", fg="#C8C0F0").pack()

        tab_frame = tk.Frame(self, bg="#ECEAF8", pady=8, padx=16)
        tab_frame.pack(fill="x")
        self.btn_members = tk.Button(tab_frame, text="👥  예배자 관리",
                                     font=("맑은 고딕", 10, "bold"),
                                     relief="flat", cursor="hand2",
                                     command=lambda: self.show_tab("members"))
        self.btn_members.pack(side="left", padx=4, ipadx=12, ipady=5)
        self.btn_attend = tk.Button(tab_frame, text="📋  출석 체크",
                                    font=("맑은 고딕", 10, "bold"),
                                    relief="flat", cursor="hand2",
                                    command=lambda: self.show_tab("attendance"))
        self.btn_attend.pack(side="left", padx=4, ipadx=12, ipady=5)

        self.content = tk.Frame(self, bg="#F8F7F4")
        self.content.pack(fill="both", expand=True, padx=16, pady=12)
        self._build_members_panel()
        self._build_attendance_panel()

    def show_tab(self, tab):
        self.current_tab = tab
        active   = dict(bg="#5038B0", fg="white")
        inactive = dict(bg="#DDDAF4", fg="#5038B0")
        if tab == "members":
            self.btn_members.config(**active)
            self.btn_attend.config(**inactive)
            self.attend_frame.pack_forget()
            self.members_frame.pack(fill="both", expand=True)
            self.refresh_members()
        else:
            self.btn_attend.config(**active)
            self.btn_members.config(**inactive)
            self.members_frame.pack_forget()
            self.attend_frame.pack(fill="both", expand=True)
            self.refresh_attendance()

    # ════════════════════════════════════════════════════════════
    #  예배자 관리 패널
    # ════════════════════════════════════════════════════════════
    def _build_members_panel(self):
        self.members_frame = tk.Frame(self.content, bg="#F8F7F4")

        # 추가 버튼 행
        top_row = tk.Frame(self.members_frame, bg="#F8F7F4")
        top_row.pack(fill="x", pady=(0, 10))
        tk.Label(top_row, text="예배자 목록", font=("맑은 고딕", 12, "bold"),
                 bg="#F8F7F4", fg="#333").pack(side="left")
        tk.Button(top_row, text="➕  예배자 추가",
                  font=("맑은 고딕", 10, "bold"),
                  bg="#5038B0", fg="white", relief="flat",
                  cursor="hand2", padx=12, pady=4,
                  command=self.open_add_dialog).pack(side="right")

        # 스크롤 목록
        lc = tk.Frame(self.members_frame, bg="#F8F7F4")
        lc.pack(fill="both", expand=True)
        self.members_canvas = tk.Canvas(lc, bg="#F8F7F4", highlightthickness=0)
        sb = ttk.Scrollbar(lc, orient="vertical", command=self.members_canvas.yview)
        self.members_canvas.configure(yscrollcommand=sb.set)
        sb.pack(side="right", fill="y")
        self.members_canvas.pack(side="left", fill="both", expand=True)
        self.members_inner = tk.Frame(self.members_canvas, bg="#F8F7F4")
        self._mcw = self.members_canvas.create_window((0,0), window=self.members_inner, anchor="nw")
        self.members_inner.bind("<Configure>", lambda e: self.members_canvas.configure(scrollregion=self.members_canvas.bbox("all")))
        self.members_canvas.bind("<Configure>", lambda e: self.members_canvas.itemconfig(self._mcw, width=e.width))

    def open_add_dialog(self):
        def on_save(name, pos, meal):
            if any(m["name"] == name for m in self.data["members"]):
                messagebox.showwarning("중복", f"'{name}'은 이미 등록된 예배자입니다.")
                return
            self.data["members"].append({
                "id": str(int(time.time() * 1000)),
                "name": name,
                "position": pos,
                "meal": meal
            })
            save_data(self.data)
            self.refresh_members()
        MemberDialog(self, on_save)

    def open_edit_dialog(self, member_id):
        member = next((m for m in self.data["members"] if m["id"] == member_id), None)
        if not member:
            return
        def on_save(name, pos, meal):
            # 다른 멤버와 이름 중복 체크
            if any(m["name"] == name and m["id"] != member_id for m in self.data["members"]):
                messagebox.showwarning("중복", f"'{name}'은 이미 등록된 예배자입니다.")
                return
            member["name"] = name
            member["position"] = pos
            member["meal"] = meal
            save_data(self.data)
            self.refresh_members()
        MemberDialog(self, on_save, member=member)

    def delete_member(self, member_id):
        member = next((m for m in self.data["members"] if m["id"] == member_id), None)
        if not member:
            return
        if messagebox.askyesno("삭제 확인", f"'{member['name']}'을(를) 삭제하시겠습니까?"):
            self.data["members"] = [m for m in self.data["members"] if m["id"] != member_id]
            save_data(self.data)
            self.refresh_members()

    def refresh_members(self):
        for w in self.members_inner.winfo_children():
            w.destroy()
        members = self.data["members"]
        if not members:
            tk.Label(self.members_inner, text="예배자를 추가해 주세요",
                     font=("맑은 고딕", 11), bg="#F8F7F4", fg="#AAAAAA").pack(pady=40)
            return

        # 헤더
        hdr = tk.Frame(self.members_inner, bg="#ECEAF8")
        hdr.pack(fill="x", padx=2, pady=(0,2))
        for text, w in [("#", 4), ("이름", 12), ("포지션", 12), ("식사", 6), ("", 16)]:
            tk.Label(hdr, text=text, width=w, font=("맑은 고딕", 9, "bold"),
                     bg="#ECEAF8", fg="#5038B0", anchor="w").pack(side="left", padx=4, pady=5)

        for i, m in enumerate(members):
            bg = "#FFFFFF" if i % 2 == 0 else "#F3F1FB"
            row = tk.Frame(self.members_inner, bg=bg,
                           highlightbackground="#DDDAF4", highlightthickness=1)
            row.pack(fill="x", pady=1, padx=2)

            tk.Label(row, text=str(i+1), width=4, font=("맑은 고딕", 9),
                     bg=bg, fg="#AAAAAA", anchor="w").pack(side="left", padx=4, pady=8)
            tk.Label(row, text="👤", font=("맑은 고딕", 11), bg=bg).pack(side="left")
            tk.Label(row, text=m["name"], width=12, font=("맑은 고딕", 11, "bold"),
                     bg=bg, fg="#222222", anchor="w").pack(side="left", padx=4)

            pos = m.get("position", "선택 안 함")
            pos_color = "#5038B0" if pos != "선택 안 함" else "#BBBBBB"
            tk.Label(row, text=pos if pos != "선택 안 함" else "-",
                     width=12, font=("맑은 고딕", 10),
                     bg=bg, fg=pos_color, anchor="w").pack(side="left", padx=4)

            meal = m.get("meal", False)
            meal_lbl = "🍚 신청" if meal else "-"
            meal_color = "#0F6E56" if meal else "#BBBBBB"
            tk.Label(row, text=meal_lbl, width=7, font=("맑은 고딕", 9),
                     bg=bg, fg=meal_color, anchor="w").pack(side="left", padx=4)

            tk.Button(row, text="✏ 수정", font=("맑은 고딕", 9), relief="flat",
                      bg="#EAF3DE", fg="#3B6D11", cursor="hand2", padx=8, pady=2,
                      command=lambda mid=m["id"]: self.open_edit_dialog(mid)
                      ).pack(side="right", padx=4, pady=6)
            tk.Button(row, text="🗑 삭제", font=("맑은 고딕", 9), relief="flat",
                      bg="#FCEBEB", fg="#A32D2D", cursor="hand2", padx=8, pady=2,
                      command=lambda mid=m["id"]: self.delete_member(mid)
                      ).pack(side="right", padx=2, pady=6)

        tk.Label(self.members_inner, text=f"총 {len(members)}명 등록됨",
                 font=("맑은 고딕", 9), bg="#F8F7F4", fg="#888888").pack(pady=(8,2))

    # ════════════════════════════════════════════════════════════
    #  출석 체크 패널
    # ════════════════════════════════════════════════════════════
    def _build_attendance_panel(self):
        self.attend_frame = tk.Frame(self.content, bg="#F8F7F4")

        # 날짜 행
        date_row = tk.Frame(self.attend_frame, bg="#F8F7F4")
        date_row.pack(fill="x", pady=(0, 8))
        tk.Label(date_row, text="📅 날짜", font=("맑은 고딕", 10),
                 bg="#F8F7F4", fg="#444").pack(side="left", padx=(0,6))
        self.date_var = tk.StringVar(value=str(date.today()))
        self._prev_date = self.date_var.get()  # 이전 날짜 추적용
        date_entry = tk.Entry(date_row, textvariable=self.date_var,
                              font=("맑은 고딕", 11), width=13,
                              relief="solid", bd=1)
        date_entry.pack(side="left", ipady=4)
        date_entry.bind("<Return>", lambda e: self._on_date_entry_changed())
        date_entry.bind("<FocusOut>", lambda e: self._on_date_entry_changed())

        tk.Button(date_row, text="📆 달력",
                  font=("맑은 고딕", 10), relief="flat",
                  bg="#DDDAF4", fg="#5038B0", cursor="hand2",
                  padx=10, pady=3,
                  command=self._open_calendar).pack(side="left", padx=6)
        tk.Button(date_row, text="오늘",
                  font=("맑은 고딕", 10), relief="flat",
                  bg="#ECEAF8", fg="#5038B0", cursor="hand2",
                  padx=8, pady=3,
                  command=self._set_today).pack(side="left", padx=2)

        # 통계 카드
        stat_frame = tk.Frame(self.attend_frame, bg="#F8F7F4")
        stat_frame.pack(fill="x", pady=(4,10))
        self.stat_labels = {}
        for key, label, color, bg in [
            ("출석", "출석", "#0F6E56", "#E1F5EE"),
            ("지각", "지각", "#854F0B", "#FAEEDA"),
            ("결석", "결석", "#A32D2D", "#FCEBEB"),
            ("식사", "식사신청", "#185FA5", "#E6F1FB"),
            ("미체크", "미체크", "#555555", "#EEEEEE"),
        ]:
            card = tk.Frame(stat_frame, bg=bg, padx=14, pady=8,
                            highlightbackground=color, highlightthickness=1,
                            cursor="hand2")
            card.pack(side="left", padx=3, ipadx=6)
            num = tk.Label(card, text="0", font=("맑은 고딕", 18, "bold"), bg=bg, fg=color,
                           cursor="hand2")
            num.pack()
            lbl = tk.Label(card, text=label, font=("맑은 고딕", 8), bg=bg, fg=color,
                           cursor="hand2")
            lbl.pack()
            self.stat_labels[key] = num
            # 카드 클릭 시 명단 팝업
            for widget in [card, num, lbl]:
                widget.bind("<Button-1>", lambda e, k=key: self._show_stat_popup(k))

        # 완료된 결과 리스트 (항상 표시, 위쪽)
        self.result_outer = tk.Frame(self.attend_frame, bg="#F8F7F4")
        self.result_outer.pack(fill="x", pady=(0, 8))

        # 구분선 + 제목
        self.result_header = tk.Frame(self.result_outer, bg="#F8F7F4")
        self.result_header.pack(fill="x")

        # 출석 체크 목록 (스크롤)
        lc = tk.Frame(self.attend_frame, bg="#F8F7F4")
        lc.pack(fill="both", expand=True)
        self.attend_canvas = tk.Canvas(lc, bg="#F8F7F4", highlightthickness=0)
        sb2 = ttk.Scrollbar(lc, orient="vertical", command=self.attend_canvas.yview)
        self.attend_canvas.configure(yscrollcommand=sb2.set)
        sb2.pack(side="right", fill="y")
        self.attend_canvas.pack(side="left", fill="both", expand=True)
        self.attend_inner = tk.Frame(self.attend_canvas, bg="#F8F7F4")
        self._acw = self.attend_canvas.create_window((0,0), window=self.attend_inner, anchor="nw")
        self.attend_inner.bind("<Configure>", lambda e: self.attend_canvas.configure(scrollregion=self.attend_canvas.bbox("all")))
        self.attend_canvas.bind("<Configure>", lambda e: self.attend_canvas.itemconfig(self._acw, width=e.width))

    def _open_calendar(self):
        CalendarPopup(self, self.date_var, self._on_date_changed)

    def _set_today(self):
        new_date = str(date.today())
        if new_date != self._prev_date:
            self._prev_date = new_date
        self.date_var.set(new_date)
        self.refresh_attendance()

    def _on_date_entry_changed(self):
        """날짜 입력창에서 직접 날짜를 변경했을 때 처리"""
        new_date = self.date_var.get().strip()
        if new_date != self._prev_date:
            self._prev_date = new_date
            self.refresh_attendance()

    def _on_date_changed(self):
        """달력에서 날짜 선택 시 처리 - 날짜 변경되면 새 날짜 데이터로 갱신"""
        new_date = self.date_var.get().strip()
        self._prev_date = new_date
        self.refresh_attendance()

    def refresh_attendance(self):
        # 결과 리스트 갱신
        self._refresh_result_list()
        # 체크 목록 갱신
        for w in self.attend_inner.winfo_children():
            w.destroy()
        members = self.data["members"]
        if not members:
            tk.Label(self.attend_inner,
                     text="먼저 [예배자 관리] 탭에서 예배자를 추가해 주세요",
                     font=("맑은 고딕", 11), bg="#F8F7F4", fg="#AAAAAA").pack(pady=40)
            self._update_stats({})
            return
        date_key = self.date_var.get().strip()
        day_data = self.data["attendance"].get(date_key, {})
        for i, m in enumerate(members):
            rec = day_data.get(m["id"], {"status": None, "reason": ""})
            self._build_attend_row(i, m, rec, date_key)
        self._update_stats(day_data)

    def _refresh_result_list(self):
        for w in self.result_header.winfo_children():
            w.destroy()

        date_key = self.date_var.get().strip()
        day_data = self.data["attendance"].get(date_key, {})
        checked = {mid: rec for mid, rec in day_data.items() if rec.get("status")}

        if not checked:
            return  # 체크된 항목 없으면 결과 리스트 숨김

        # 제목
        title_row = tk.Frame(self.result_header, bg="#5038B0")
        title_row.pack(fill="x", pady=(0, 4))
        tk.Label(title_row, text=f"  📋 {date_key}  출석 현황",
                 font=("맑은 고딕", 10, "bold"),
                 bg="#5038B0", fg="white").pack(side="left", pady=5)

        STATUS_COLOR = {"출석": ("#0F6E56", "#E1F5EE"), "지각": ("#854F0B", "#FAEEDA"), "결석": ("#A32D2D", "#FCEBEB")}

        for mid, rec in checked.items():
            member = next((m for m in self.data["members"] if m["id"] == mid), None)
            if not member:
                continue
            status = rec.get("status", "")
            reason = rec.get("reason", "")
            fg, bg = STATUS_COLOR.get(status, ("#333", "#EEE"))
            pos = member.get("position", "선택 안 함")
            pos_text = f"  [{pos}]" if pos != "선택 안 함" else ""
            meal = "  🍚" if member.get("meal") else ""

            row = tk.Frame(self.result_header, bg=bg,
                           highlightbackground=fg, highlightthickness=1)
            row.pack(fill="x", pady=1, padx=2)
            name_str = f"{member['name']}{pos_text}{meal}"
            tk.Label(row, text=name_str, font=("맑은 고딕", 10, "bold"),
                     bg=bg, fg=fg, anchor="w").pack(side="left", padx=10, pady=5)
            status_badge = tk.Label(row, text=f" {status} ",
                                    font=("맑은 고딕", 9, "bold"),
                                    bg=fg, fg="white")
            status_badge.pack(side="left", padx=4)
            if reason:
                tk.Label(row, text=f"사유: {reason}",
                         font=("맑은 고딕", 9), bg=bg, fg=fg, anchor="w"
                         ).pack(side="left", padx=6)

        tk.Frame(self.result_header, bg="#DDDAF4", height=1).pack(fill="x", pady=6)
        tk.Label(self.result_header, text="▼ 아래에서 출석을 체크하세요",
                 font=("맑은 고딕", 9), bg="#F8F7F4", fg="#888888").pack(pady=(0,4))

    def _build_attend_row(self, idx, member, rec, date_key):
        bg = "#FFFFFF" if idx % 2 == 0 else "#F9F8FD"
        outer = tk.Frame(self.attend_inner, bg=bg,
                         highlightbackground="#E0DEEE", highlightthickness=1)
        outer.pack(fill="x", pady=2, padx=2)

        top = tk.Frame(outer, bg=bg)
        top.pack(fill="x")

        tk.Label(top, text=str(idx+1), width=3, font=("맑은 고딕", 9),
                 bg=bg, fg="#BBBBBB").pack(side="left", padx=(8,0), pady=8)
        tk.Label(top, text="👤", font=("맑은 고딕", 11), bg=bg).pack(side="left", padx=4)

        # 이름 + 포지션 + 식사
        name_frame = tk.Frame(top, bg=bg)
        name_frame.pack(side="left")
        tk.Label(name_frame, text=member["name"],
                 font=("맑은 고딕", 11, "bold"), bg=bg, fg="#222222").pack(side="left")
        pos = member.get("position", "선택 안 함")
        if pos != "선택 안 함":
            tk.Label(name_frame, text=f"  {pos}",
                     font=("맑은 고딕", 9), bg=bg, fg="#5038B0").pack(side="left")
        if member.get("meal"):
            tk.Label(name_frame, text="  🍚",
                     font=("맑은 고딕", 9), bg=bg, fg="#0F6E56").pack(side="left")

        # 상태 버튼
        btn_frame = tk.Frame(top, bg=bg)
        btn_frame.pack(side="right", padx=8, pady=6)

        STATUS_STYLES = {
            "출석": {"active_bg":"#1D9E75","active_fg":"white","inactive_bg":"#E1F5EE","inactive_fg":"#0F6E56","label":"✔ 출석"},
            "지각": {"active_bg":"#EF9F27","active_fg":"white","inactive_bg":"#FAEEDA","inactive_fg":"#854F0B","label":"⏰ 지각"},
            "결석": {"active_bg":"#E24B4A","active_fg":"white","inactive_bg":"#FCEBEB","inactive_fg":"#A32D2D","label":"✖ 결석"},
        }
        cur = rec.get("status")
        for status, s in STATUS_STYLES.items():
            active = cur == status
            tk.Button(btn_frame, text=s["label"],
                      font=("맑은 고딕", 9, "bold" if active else "normal"),
                      relief="flat",
                      bg=s["active_bg"] if active else s["inactive_bg"],
                      fg=s["active_fg"] if active else s["inactive_fg"],
                      cursor="hand2", padx=8, pady=3,
                      command=lambda m=member, st=status, dk=date_key: self._set_status(m, st, dk)
                      ).pack(side="left", padx=2)

        # 식사 여부 토글 버튼 (출석 체크 행에 통합)
        meal_active = member.get("meal", False)
        meal_btn_bg = "#185FA5" if meal_active else "#E6F1FB"
        meal_btn_fg = "white" if meal_active else "#185FA5"
        meal_btn_text = "🍚 식사 O" if meal_active else "🍚 식사 X"
        tk.Button(btn_frame, text=meal_btn_text,
                  font=("맑은 고딕", 9, "bold" if meal_active else "normal"),
                  relief="flat",
                  bg=meal_btn_bg, fg=meal_btn_fg,
                  cursor="hand2", padx=8, pady=3,
                  command=lambda m=member: self._toggle_meal(m)
                  ).pack(side="left", padx=(6, 2))

        # 사유 입력
        if cur in ("지각", "결석"):
            rf = tk.Frame(outer, bg=bg)
            rf.pack(fill="x", padx=(50,8), pady=(0,8))
            color = "#854F0B" if cur == "지각" else "#A32D2D"
            tk.Label(rf, text="사유:", font=("맑은 고딕", 9), bg=bg, fg=color
                     ).pack(side="left", padx=(0,4))
            rv = tk.StringVar(value=rec.get("reason", ""))
            entry = tk.Entry(rf, textvariable=rv, font=("맑은 고딕", 10),
                             width=32, relief="solid", bd=1)
            entry.pack(side="left", ipady=3, fill="x", expand=True)

            def save_reason(event=None, mid=member["id"], r=rv, dk=date_key):
                if dk in self.data["attendance"] and mid in self.data["attendance"][dk]:
                    self.data["attendance"][dk][mid]["reason"] = r.get()
                    save_data(self.data)
                    self._refresh_result_list()  # 결과 리스트 즉시 갱신

            entry.bind("<FocusOut>", save_reason)
            entry.bind("<Return>", save_reason)

    def _toggle_meal(self, member):
        """출석 체크 행에서 식사 여부 토글"""
        member["meal"] = not member.get("meal", False)
        save_data(self.data)
        self.refresh_attendance()

    def _show_stat_popup(self, key):
        """통계 카드 클릭 시 해당 명단 팝업 표시"""
        date_key = self.date_var.get().strip()
        day_data = self.data["attendance"].get(date_key, {})

        COLOR_MAP = {
            "출석": ("#0F6E56", "#E1F5EE"),
            "지각": ("#854F0B", "#FAEEDA"),
            "결석": ("#A32D2D", "#FCEBEB"),
            "식사": ("#185FA5", "#E6F1FB"),
            "미체크": ("#555555", "#EEEEEE"),
        }
        LABEL_MAP = {"출석": "출석", "지각": "지각", "결석": "결석", "식사": "식사 신청", "미체크": "미체크"}
        fg, bg = COLOR_MAP[key]

        # 해당 카테고리 멤버 목록 수집
        if key == "식사":
            members_in = [m for m in self.data["members"] if m.get("meal")]
            members_with_rec = None
        elif key == "미체크":
            checked_ids = {mid for mid, rec in day_data.items() if rec.get("status")}
            members_in = [m for m in self.data["members"] if m["id"] not in checked_ids]
            members_with_rec = None
        else:
            members_with_rec = []
            for m in self.data["members"]:
                rec = day_data.get(m["id"], {})
                if rec.get("status") == key:
                    members_with_rec.append((m, rec))
            members_in = None

        # 팝업 창
        popup = tk.Toplevel(self)
        popup.title(f"{LABEL_MAP[key]} 명단")
        popup.resizable(False, False)
        popup.configure(bg="#F8F7F4")
        popup.grab_set()
        popup.minsize(320, 200)

        # 헤더
        hdr = tk.Frame(popup, bg=fg, pady=10)
        hdr.pack(fill="x")
        count = len(members_with_rec) if members_with_rec is not None else len(members_in)
        tk.Label(hdr, text=f"{LABEL_MAP[key]}  —  총 {count}명",
                 font=("맑은 고딕", 13, "bold"),
                 bg=fg, fg="white").pack()
        tk.Label(hdr, text=date_key,
                 font=("맑은 고딕", 9), bg=fg, fg="white").pack()

        if count == 0:
            tk.Label(popup, text="해당 인원이 없습니다.",
                     font=("맑은 고딕", 11), bg="#F8F7F4", fg="#AAAAAA",
                     pady=30, padx=40).pack()
        else:
            list_frame = tk.Frame(popup, bg="#F8F7F4")
            list_frame.pack(fill="both", expand=True, padx=16, pady=12)

            if key in ("출석", "지각", "결석"):
                for i, (m, rec) in enumerate(members_with_rec):
                    row_bg = "#FFFFFF" if i % 2 == 0 else bg
                    row = tk.Frame(list_frame, bg=row_bg,
                                   highlightbackground=fg, highlightthickness=1)
                    row.pack(fill="x", pady=2)
                    pos = m.get("position", "선택 안 함")
                    pos_text = f"  [{pos}]" if pos != "선택 안 함" else ""
                    meal_text = "  🍚" if m.get("meal") else ""
                    name_str = f"👤  {m['name']}{pos_text}{meal_text}"
                    tk.Label(row, text=name_str, font=("맑은 고딕", 11, "bold"),
                             bg=row_bg, fg=fg, anchor="w").pack(side="left", padx=12, pady=7)
                    reason = rec.get("reason", "")
                    if reason:
                        tk.Label(row, text=f"사유: {reason}",
                                 font=("맑은 고딕", 9), bg=row_bg, fg=fg,
                                 anchor="w").pack(side="left", padx=6)
            else:
                for i, m in enumerate(members_in):
                    row_bg = "#FFFFFF" if i % 2 == 0 else bg
                    row = tk.Frame(list_frame, bg=row_bg,
                                   highlightbackground=fg, highlightthickness=1)
                    row.pack(fill="x", pady=2)
                    pos = m.get("position", "선택 안 함")
                    pos_text = f"  [{pos}]" if pos != "선택 안 함" else ""
                    name_str = f"👤  {m['name']}{pos_text}"
                    tk.Label(row, text=name_str, font=("맑은 고딕", 11, "bold"),
                             bg=row_bg, fg=fg, anchor="w").pack(side="left", padx=12, pady=7)

        tk.Button(popup, text="닫기", font=("맑은 고딕", 10, "bold"),
                  bg=fg, fg="white", relief="flat",
                  padx=20, pady=6, cursor="hand2",
                  command=popup.destroy).pack(pady=(4, 16))

    def _set_status(self, member, status, date_key):
        if not date_key:
            messagebox.showwarning("날짜 오류", "날짜를 먼저 선택해 주세요.")
            return
        if date_key not in self.data["attendance"]:
            self.data["attendance"][date_key] = {}
        day = self.data["attendance"][date_key]
        cur = day.get(member["id"], {}).get("status")
        if cur == status:
            day.pop(member["id"], None)
        else:
            day[member["id"]] = {"status": status, "reason": ""}
        save_data(self.data)
        self.refresh_attendance()

    def _update_stats(self, day_data):
        total = len(self.data["members"])
        counts = {"출석": 0, "지각": 0, "결석": 0}
        for mid, rec in day_data.items():
            s = rec.get("status")
            if s in counts:
                counts[s] += 1
        checked = sum(counts.values())
        meal_count = sum(1 for m in self.data["members"] if m.get("meal"))
        self.stat_labels["출석"].config(text=str(counts["출석"]))
        self.stat_labels["지각"].config(text=str(counts["지각"]))
        self.stat_labels["결석"].config(text=str(counts["결석"]))
        self.stat_labels["식사"].config(text=str(meal_count))
        self.stat_labels["미체크"].config(text=str(total - checked))

# ── 실행 ─────────────────────────────────────────────────────────
if __name__ == "__main__":
    if not HAS_CAL:
        import subprocess, sys
        print("=" * 50)
        print("tkcalendar 미설치 — 달력 기능이 제한됩니다.")
        print("설치 명령어: pip install tkcalendar")
        print("=" * 50)
    app = WorshipApp()
    app.mainloop()
