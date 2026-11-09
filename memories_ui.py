"""Memories window: see and edit what the characters remember about you."""
from PySide6.QtWidgets import (QDialog, QDialogButtonBox, QHBoxLayout, QLabel, QLineEdit, QListWidget, QPlainTextEdit,
                               QPushButton, QVBoxLayout, QWidget)

from memory import MAX_PINNED


def _list_box(items, title, add=False):
    """A titled list with Remove (and an Add field); returns (widget, the list)."""
    box = QWidget()
    lay = QVBoxLayout(box)
    lay.setContentsMargins(0, 0, 0, 0)
    lay.addWidget(QLabel(title))
    lst = QListWidget()
    lst.addItems(items)
    lst.setWordWrap(True)
    lay.addWidget(lst)
    row = QWidget()
    buttons = QHBoxLayout(row)
    buttons.setContentsMargins(0, 0, 0, 0)
    if add:
        field = QLineEdit()
        field.setPlaceholderText("Something they should always remember...")
        plus = QPushButton("Add")
        def add_fact():
            if lst.count() >= MAX_PINNED:
                return field.setPlaceholderText(f"Full ({MAX_PINNED}): remove some first")
            if field.text().strip():
                lst.addItem(field.text().strip())
            field.clear()

        plus.clicked.connect(add_fact)
        field.returnPressed.connect(plus.click)
        buttons.addWidget(field)
        buttons.addWidget(plus)
    remove = QPushButton("Remove selected")
    remove.clicked.connect(lambda: [lst.takeItem(lst.row(i)) for i in lst.selectedItems()])
    buttons.addWidget(remove)
    lay.addWidget(row)
    return box, lst


class MemoriesWindow(QDialog):
    def __init__(self, mem, name):
        super().__init__()
        self.mem = mem
        self.setWindowTitle(f"What {name} remembers about you")
        self.resize(620, 680)
        with mem.lock:
            profile, pinned, notes = mem.d["profile"], list(mem.d["pinned"]), list(mem.d["notes"])
        lay = QVBoxLayout(self)
        lay.addWidget(QLabel("Long-term picture of you (old notes get folded in here, so nothing lasting is lost):"))
        self.profile = QPlainTextEdit(profile)
        self.profile.setMaximumHeight(130)
        lay.addWidget(self.profile)
        title = f'Always remembered, {len(pinned)} of {MAX_PINNED} (also: "Hey {name}, remember that ..." / "forget ..."):'
        box, self.pinned = _list_box(pinned, title, add=True)
        lay.addWidget(box)
        box, self.notes = _list_box(notes, "Recent notes they took on their own:")
        lay.addWidget(box)
        buttons = QDialogButtonBox(QDialogButtonBox.Save | QDialogButtonBox.Cancel)
        buttons.accepted.connect(self.save)
        buttons.rejected.connect(self.reject)
        lay.addWidget(buttons)

    def save(self):
        with self.mem.lock:
            self.mem.d["profile"] = self.profile.toPlainText().strip()
            self.mem.d["pinned"] = [self.pinned.item(i).text() for i in range(self.pinned.count())]
            self.mem.d["notes"] = [self.notes.item(i).text() for i in range(self.notes.count())]
        self.mem.save()
        self.accept()
