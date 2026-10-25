"""Native themed buttons aligned with visible movie Treeview rows."""
from tkinter import ttk


class MovieRowActions:
    def __init__(self, view, command):
        self.view = view
        self.command = command
        self.scheduler = view.winfo_toplevel()
        self.closed = False
        self.buttons = {}
        self.pending = None
        for column in ("play", "delete"):
            view.column(column, stretch=False, anchor="center")
            view.heading(column, command="")
        # Preserve the scrollbars and resync after scrolling in either direction.
        for axis in ("x", "y"):
            previous = view.cget(axis + "scrollcommand")
            def scroll(first, last, previous=previous):
                if previous:
                    view.tk.call(previous, first, last)
                self.schedule()
            view.configure(**{axis + "scrollcommand": scroll})
        for event in ("<Configure>", "<Map>", "<ButtonRelease-1>", "<KeyRelease>"):
            view.bind(event, self.schedule, add="+")
        view.bind("<Destroy>", self.close, add="+")

    def schedule(self, event=None):
        if not self.closed and self.pending is None:
            self.pending = self.scheduler.after_idle(self.sync)

    def sync(self):
        self.pending = None
        view = self.view
        visible = set()
        if view.winfo_ismapped():
            # Only instantiate controls for visible rows, including long libraries.
            for item in view.get_children():
                box = view.bbox(item)
                if not box:
                    continue
                visible.add(item)
                if item not in self.buttons:
                    self.buttons[item] = tuple(
                        ttk.Button(view, text=label, width=width, padding=(3, 0),
                                   command=lambda i=item, a=action: self.command(i, a))
                        for action, label, width in (("play", "Play", 5), ("delete", "Delete", 6)))
                for column, button in zip(("play", "delete"), self.buttons[item]):
                    required = button.winfo_reqwidth() + 4
                    if view.column(column, "width") != required:
                        view.column(column, width=required, minwidth=required)
                    cell = view.bbox(item, column)
                    if cell:
                        x, y, width, height = cell
                        # Hide partially clipped controls rather than overlap adjacent cells.
                        if x >= 0 and x + width <= view.winfo_width():
                            button.place(x=x + 2, y=y + 1, width=width - 4, height=height - 2)
                            continue
                    button.place_forget()
        for item in set(self.buttons) - visible:
            for button in self.buttons.pop(item):
                button.destroy()

    def close(self, event):
        if event.widget == self.view:
            self.closed = True
            if self.pending is not None:
                self.scheduler.after_cancel(self.pending)
                self.pending = None
