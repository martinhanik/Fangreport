# Copyright (c) 2026 Martin Hanik
#
# This source code is licensed under the MIT license found in the
# LICENSE file in the root directory of this source tree.

import threading
import tkinter as tk
from tkinter import filedialog, messagebox, ttk
from datetime import datetime

from fangreport.core import generate_catch_report


class FangreportApp(tk.Tk):
    """
    GUI zur Erstellung eines Fangreports.
    """
    def __init__(self):
        super().__init__()

        self.title("Fangreport")
        self.geometry("720x820")
        self.minsize(680, 760)

        self.photo_path_var = tk.StringVar()
        self.status_var = tk.StringVar(value="Bereit.")

        self._build_ui()

    def _build_ui(self):
        self.columnconfigure(0, weight=1)
        self.rowconfigure(0, weight=1)
        self.rowconfigure(1, weight=0)

        main_frame = ttk.Frame(self, padding=16)
        main_frame.grid(row=0, column=0, sticky="nsew")
        main_frame.columnconfigure(0, weight=1)

        button_frame = ttk.Frame(self, padding=(16, 8, 16, 16))
        button_frame.grid(row=1, column=0, sticky="ew")
        button_frame.columnconfigure(0, weight=1)

        title_label = ttk.Label(
            main_frame,
            text="🎣 Fangreport erstellen",
            font=("TkDefaultFont", 18, "bold")
        )
        title_label.pack(anchor="w", pady=(0, 12))

        form_frame = ttk.LabelFrame(main_frame, text="Fangdaten", padding=12)
        form_frame.pack(fill="x", pady=(0, 12))

        self.entries = {}

        fields = [
            ("Fischart", "z. B. Wels", True),
            ("Länge", "cm, z. B. 130", False),
            ("Gewicht", "kg, z. B. 8.5", False),
            ("Datum", "YYYY-MM-DD", True),
            ("Zeit", "HH:MM", True),
            ("Breiten- und Längengrad", "z. B. 49.357599616156776, 8.494281048199765", True),
            ("Pegelstation", "z. B. Speyer", True),
            ("Wassertemperatur", "°C, z. B. 12.5", False),
            ("Trübung", "z. B. klar", False),
        ]

        for row, (label, placeholder, required) in enumerate(fields):
            label_text = f"{label} *" if required else label
            ttk.Label(form_frame, text=label_text).grid(
                row=row,
                column=0,
                sticky="w",
                padx=(0, 12),
                pady=5
            )

            entry = ttk.Entry(form_frame)
            entry.grid(row=row, column=1, sticky="ew", pady=5)

            entry.insert(0, placeholder)
            entry.configure(foreground="gray")

            entry.placeholder = placeholder
            entry.placeholder_active = True

            entry.bind(
                "<FocusIn>",
                self._clear_placeholder
            )
            entry.bind(
                "<FocusOut>",
                self._restore_placeholder
            )

            self.entries[label] = {
                "widget": entry,
                "placeholder": placeholder,
                "required": required
            }

        form_frame.columnconfigure(1, weight=1)

        self.entries["Fischart"]["widget"].delete(0, tk.END)
        self.entries["Fischart"]["widget"].insert(0, "Wels")
        self.entries["Fischart"]["widget"].configure(foreground="white")
        self.entries["Fischart"]["widget"].placeholder_active = False

        photo_frame = ttk.LabelFrame(main_frame, text="Foto", padding=12)
        photo_frame.pack(fill="x", pady=(0, 12))

        ttk.Entry(
            photo_frame,
            textvariable=self.photo_path_var,
            state="readonly"
        ).pack(side="left", fill="x", expand=True, padx=(0, 8))

        ttk.Button(
            photo_frame,
            text="Foto auswählen ...",
            command=self._select_photo
        ).pack(side="left")

        ttk.Button(
            photo_frame,
            text="Entfernen",
            command=lambda: self.photo_path_var.set("")
        ).pack(side="left", padx=(8, 0))
        notes_frame = ttk.LabelFrame(main_frame, text="Notizen", padding=8)
        notes_frame.pack(fill="x", pady=(0, 12))

        self.notes_text = tk.Text(notes_frame, height=5, wrap="word")
        self.notes_text.pack(side="left", fill="x", expand=True)

        notes_scrollbar = ttk.Scrollbar(
            notes_frame,
            orient="vertical",
            command=self.notes_text.yview
        )
        notes_scrollbar.pack(side="right", fill="y")
        self.notes_text.configure(yscrollcommand=notes_scrollbar.set)

        hint_label = ttk.Label(
            main_frame,
            text="* Pflichtfelder. Die Skizzenfläche bleibt im PDF frei und kann später von Hand ausgefüllt werden.",
            foreground="#555555"
        )
        hint_label.pack(anchor="w", pady=(0, 8))

        status_label = ttk.Label(
            button_frame,
            textvariable=self.status_var,
            foreground="#1f4e79"
        )
        status_label.grid(row=0, column=0, sticky="w", pady=(0, 8), columnspan=2)

        self.create_button = ttk.Button(
            button_frame,
            text="Fangreport erstellen",
            command=self._start_report_generation
        )
        self.create_button.grid(row=1, column=0, sticky="ew", padx=(0, 8), ipady=8)

        close_button = ttk.Button(
            button_frame,
            text="Schließen",
            command=self.destroy
        )
        close_button.grid(row=1, column=1, sticky="e")

    @staticmethod
    def _clear_placeholder(event):
        entry = event.widget

        if getattr(entry, "placeholder_active", False):
            entry.delete(0, tk.END)
            entry.configure(foreground="white")
            entry.placeholder_active = False

    @staticmethod
    def _restore_placeholder(event):
        entry = event.widget

        if not entry.get().strip():
            entry.insert(0, entry.placeholder)
            entry.configure(foreground="gray")
            entry.placeholder_active = True

    def _get_entry_value(self, label):
        entry_data = self.entries[label]
        entry = entry_data["widget"]
        value = entry.get().strip()

        if entry.cget("foreground") == "gray":
            return ""

        return value

    def _select_photo(self):
        file_path = filedialog.askopenfilename(
            title="Fangfoto auswählen",
            filetypes=[
                ("Bilddateien", "*.jpg *.jpeg *.png *.bmp *.gif *.tiff"),
                ("Alle Dateien", "*.*")
            ]
        )

        if file_path:
            self.photo_path_var.set(file_path)

    def _validate_and_collect_data(self):
        missing_fields = []

        for label, entry_data in self.entries.items():
            if entry_data["required"] and not self._get_entry_value(label):
                missing_fields.append(label)

        if missing_fields:
            raise ValueError(
                "Bitte fülle die folgenden Pflichtfelder aus:\n"
                + ", ".join(missing_fields)
            )

        date = self._get_entry_value("Datum")
        time_of_catch = self._get_entry_value("Zeit")
        species = self._get_entry_value("Fischart")
        station = self._get_entry_value("Pegelstation")
        water_clarity = self._get_entry_value("Trübung") or "Keine Daten"
        photo_path = self.photo_path_var.get().strip() or None
        notes = self.notes_text.get("1.0", tk.END).strip()

        try:
            datetime.strptime(date, "%Y-%m-%d")
        except ValueError as exc:
            raise ValueError("Das Datum muss im Format YYYY-MM-DD eingegeben werden.") from exc

        try:
            datetime.strptime(time_of_catch, "%H:%M")
        except ValueError as exc:
            raise ValueError("Die Zeit muss im Format HH:MM eingegeben werden.") from exc

        try:
            c = self._get_entry_value("Breiten- und Längengrad").split(",")

            if len(c) != 2:
                raise ValueError("Es müssen genau zwei Werte angegeben werden.")

            latitude = float(c[0].strip())
            longitude = float(c[1].strip())

        except ValueError as exc:
            raise ValueError(
                "Längen- und Breitengrad müssen zwei durch ein Komma getrennte Zahlen sein, "
                "deren Nachkommastellen durch einen Punkt angezeigt werden."
            ) from exc

        if not -90 <= latitude <= 90:
            raise ValueError("Der Breitengrad muss zwischen -90 und 90 liegen.")

        if not -180 <= longitude <= 180:
            raise ValueError("Der Längengrad muss zwischen -180 und 180 liegen.")

        fish_length_text = self._get_entry_value("Länge")
        fish_length = None
        if not (fish_length_text is None or fish_length_text == "cm, z. B. 130"):
            try:
                fish_length = float(fish_length_text.replace(",", "."))
            except ValueError as exc:
                raise ValueError("Die Fischlänge muss eine Zahl sein.") from exc

        fish_weight_text = self._get_entry_value("Gewicht")
        fish_weight = None
        if not (fish_weight_text is None or fish_weight_text == "kg, z. B. 8.5"):
            try:
                fish_weight = float(
                    fish_weight_text.replace(",", ".")
                )
            except ValueError as exc:
                raise ValueError(
                    "Das Fischgewicht muss eine Zahl sein."
                ) from exc

        water_temperature_text = self._get_entry_value("Wassertemperatur")
        water_temperature = None
        if not (water_temperature_text is None or water_temperature_text == "optional, °C"):
            try:
                water_temperature = float(water_temperature_text.replace(",", "."))
            except ValueError as exc:
                raise ValueError("Die Wassertemperatur muss eine Zahl sein.") from exc

        catch_datetime = datetime.strptime(f"{date} {time_of_catch}", "%Y-%m-%d %H:%M")
        if datetime.now() < catch_datetime:
            raise ValueError("Das Fangdatum liegt in der Zukunft.")

        return {
            "date": date,
            "time_of_catch": time_of_catch,
            "station": station,
            "latitude": latitude,
            "longitude": longitude,
            "water_temperature_at_catch": water_temperature,
            "species": species,
            "fish_length": fish_length,
            "fish_weight": fish_weight,
            "water_clarity": water_clarity,
            "photo_path": photo_path,
            "notes": notes,
        }

    def _start_report_generation(self):
        try:
            report_args = self._validate_and_collect_data()
        except ValueError as exc:
            messagebox.showerror("Eingabefehler", str(exc))
            return

        self.create_button.configure(state="disabled")
        self.status_var.set("Fangreport wird erstellt ...")

        worker = threading.Thread(
            target=self._generate_report_worker,
            args=(report_args,),
            daemon=True
        )
        worker.start()

    def _generate_report_worker(self, report_args):
        try:
            generate_catch_report(**report_args)
        except SystemExit as exc:
            self.after(
                0,
                lambda: self._report_failed(
                    f"Der Report konnte nicht erstellt werden. Details siehe Konsole.\n\n{exc}"
                )
            )
        except Exception as exc:
            self.after(0, lambda msg=str(exc): self._report_failed(msg))
        else:
            self.after(0, self._report_finished)

    def _report_finished(self):
        self.create_button.configure(state="normal")
        self.status_var.set("Fangreport wurde erfolgreich erstellt.")
        messagebox.showinfo(
            "Fangreport erstellt",
            "Der Fangreport wurde erfolgreich erstellt und im Ordner „fänge“ gespeichert."
        )

    def _report_failed(self, message):
        self.create_button.configure(state="normal")
        self.status_var.set("Fehler beim Erstellen des Fangreports.")
        messagebox.showerror("Fehler", message)


if __name__ == "__main__":
    app = FangreportApp()
    app.mainloop()