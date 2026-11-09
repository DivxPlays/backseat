"""What you're listening to on Spotify, read from the Spotify app's window title: "Artist - Song" while it plays, just
"Spotify ..." when paused. All on this PC: no Spotify login. The song only goes out as context in their lines.
"""
import ctypes
from ctypes import wintypes

user32, kernel32 = ctypes.windll.user32, ctypes.windll.kernel32
_EACH_WINDOW = ctypes.WINFUNCTYPE(wintypes.BOOL, wintypes.HWND, wintypes.LPARAM)
_exes = {}  # pid -> exe path (a window's program doesn't change)


def _exe(pid):
    if pid not in _exes:
        exe = ""
        h = kernel32.OpenProcess(0x1000, False, pid)  # PROCESS_QUERY_LIMITED_INFORMATION
        if h:
            buf, size = ctypes.create_unicode_buffer(1024), wintypes.DWORD(1024)
            if kernel32.QueryFullProcessImageNameW(h, 0, buf, ctypes.byref(size)):
                exe = buf.value
            kernel32.CloseHandle(h)
        _exes[pid] = exe
    return _exes[pid]


def spotify_titles():
    """The titles of the Spotify app's windows."""
    titles = []

    def each(hwnd, _):
        n = user32.GetWindowTextLengthW(hwnd)
        if n:
            pid = wintypes.DWORD()
            user32.GetWindowThreadProcessId(hwnd, ctypes.byref(pid))
            if _exe(pid.value).lower().endswith("\\spotify.exe"):
                title = ctypes.create_unicode_buffer(n + 1)
                user32.GetWindowTextW(hwnd, title, n + 1)
                titles.append(title.value)
        return True

    user32.EnumWindows(_EACH_WINDOW(each), 0)
    return titles


def parse(title):
    """"Artist - Song" -> (artist, song). Paused or idle ("Spotify Premium"), or an ad -> None."""
    if " - " not in title or title.lower().startswith(("spotify", "advertisement")):
        return None
    artist, song = (part.strip() for part in title.split(" - ", 1))  # a song name can have " - " in it too
    return (artist, song) if artist and song else None


def now_playing():
    """(artist, song) Spotify is playing right now, or None."""
    for title in spotify_titles():
        hit = parse(title)
        if hit:
            return hit
    return None


class Listening:
    """This session: what's playing, since when, and how often each song has come on (repeats)."""

    def __init__(self):
        self.now, self.since, self.plays = None, 0.0, {}

    def update(self, playing, now):
        """Note what's playing; True when a different song just started."""
        if playing == self.now:
            return False
        self.now, self.since = playing, now
        if playing:
            self.plays[playing] = self.plays.get(playing, 0) + 1
        return bool(playing)
