"""Ефект «цифрового дощу» з фільму «Матриця» у терміналі.

Запуск: python3 Matrix.py
Вихід:  Ctrl+C
"""

import os
import random
import sys
import time

# --- НАБІР СИМВОЛІВ ---
# Напівширинна катакана — саме її використали у фільмі. Вона моноширинна,
# тому сітка не «розповзається»: повноширинні знаки (アカサ) займають у
# терміналі два стовпці й ламають вирівнювання.
KATAKANA = "ﾊﾐﾋｰｳｼﾅﾓﾆｻﾜﾂｵﾘｱﾎﾃﾏｹﾒｴｶｷﾑﾕﾗｾﾈｽﾀﾇﾍｦｲｸｺｿﾁﾄﾉﾌﾔﾖﾙﾚﾛﾝ"
DIGITS_AND_SIGNS = "0123456789Z:.=*+-<>¦"
CHARS = KATAKANA * 3 + DIGITS_AND_SIGNS

# --- НАЛАШТУВАННЯ ---
# Усе задано в одиницях часу, тому зміна FPS впливає лише на плавність
# картинки, а не на темп анімації.
FPS = 60
FALL_SPEED = (1.5, 5.0)    # рядків за секунду
TRAIL_LEN = (10, 34)       # довжина хвоста в символах
DROPS_PER_SEC = 0.07       # скільки крапель за секунду запускає один стовпець
FLICKER_PER_SEC = 2.0      # скільки символів за секунду змінюється в стовпці
FIXED_SIZE = None          # напр. (120, 40); None — усе вікно терміналу
FALLBACK_SIZE = (120, 40)  # якщо вивід не в термінал і розмір невідомий

# --- КОЛЬОРИ ---
TRAIL_RGB = (0, 255, 70)    # зелений хвіст
HEAD_RGB = (225, 255, 230)  # майже біла голова краплі
GAMMA = 1.6                 # >1 робить згасання довшим і м'якшим
SHADES = 32                 # градацій яскравості хвоста
GLOW_STEPS = 16             # градацій підсвітки при переході між клітинками

# Truecolor підтримують майже всі сучасні термінали. Там, де його немає,
# лишається ступінчата, але робоча палітра з 256 кольорів.
TRUECOLOR = os.environ.get("COLORTERM", "").lower() in ("truecolor", "24bit")
GREEN_256 = (16, 22, 22, 28, 34, 40, 46, 47, 48, 84, 120, 157, 194)

# --- КЕРУВАННЯ ТЕРМІНАЛОМ ---
RESET = "\033[0m"
HOME = "\033[H"
CLEAR = "\033[2J"
# альтернативний екран, сховати курсор, вимкнути автоперенос рядків
ENTER_SCREEN = "\033[?1049h\033[?25l\033[?7l" + CLEAR
EXIT_SCREEN = "\033[?7h\033[?25h\033[?1049l" + RESET


def _mix(rgb_from, rgb_to, weight):
    """Проміжний колір між двома: weight 0.0 — перший, 1.0 — другий."""
    return tuple(round(a + (b - a) * weight) for a, b in zip(rgb_from, rgb_to))


def _code(rgb, level):
    """ANSI-код кольору rgb, приглушеного до яскравості level (0.0 - 1.0)."""
    if TRUECOLOR:
        red, green, blue = (round(channel * level) for channel in rgb)
        return f"\033[38;2;{red};{green};{blue}m"
    index = min(int(level * len(GREEN_256)), len(GREEN_256) - 1)
    return f"\033[38;5;{GREEN_256[index]}m"


# Хвіст: індекс — яскравість клітинки від 0 до SHADES-1.
TRAIL_PALETTE = tuple(
    _code(TRAIL_RGB, (level / (SHADES - 1)) ** GAMMA) for level in range(SHADES)
)
# Клітинка, у якій голова зараз стоїть: чим далі голова з неї вийшла,
# тим більше білого змінюється на зелений.
HEAD_PALETTE = tuple(
    _code(_mix(TRAIL_RGB, HEAD_RGB, step / GLOW_STEPS), 1.0)
    for step in range(GLOW_STEPS + 1)
)
# Клітинка, у яку голова входить: розсвічується разом із наближенням
# голови — саме це прибирає «сходинки» на малих швидкостях.
LEAD_PALETTE = tuple(
    _code(_mix(TRAIL_RGB, HEAD_RGB, step / GLOW_STEPS), step / GLOW_STEPS)
    for step in range(GLOW_STEPS + 1)
)


def terminal_size():
    """Розмір полотна: усе вікно терміналу (або FIXED_SIZE, якщо задано).

    Розмір питаємо напряму в терміналу: shutil.get_terminal_size() спершу
    дивиться на COLUMNS/LINES, а вони в IDE-консолях і в tmux часто
    застарілі — через це кадр займав лише частину вікна.
    """
    if FIXED_SIZE:
        return FIXED_SIZE
    for stream in (sys.__stdout__, sys.__stderr__, sys.__stdin__):
        try:
            size = os.get_terminal_size(stream.fileno())
        except (OSError, ValueError, AttributeError):
            continue  # потік не термінал — пробуємо наступний
        if size.columns and size.lines:
            return max(size.columns, 20), max(size.lines, 10)
    return FALLBACK_SIZE


class Drop:
    """Крапля: голова, що спускається одним стовпцем, і слід за нею."""

    __slots__ = ("y", "speed", "fade", "painted", "char")

    def __init__(self):
        self.y = 0.0
        self.speed = random.uniform(*FALL_SPEED)
        # Слід гасне рівно стільки часу, скільки голова проходить
        # TRAIL_LEN клітинок, тому довжина хвоста не залежить від швидкості.
        self.fade = self.speed / random.randint(*TRAIL_LEN)
        self.painted = -1  # останній намальований рядок
        self.char = random.choice(CHARS)  # символ клітинки, у яку входить голова


class Rain:
    """Сітка символів і краплі, що спускаються стовпцями."""

    def __init__(self, columns, rows):
        self.resize(columns, rows)

    def resize(self, columns, rows):
        self.columns = columns
        self.rows = rows
        self.chars = [[" "] * columns for _ in range(rows)]
        self.bright = [[0.0] * columns for _ in range(rows)]  # яскравість хвоста
        self.fade = [[0.0] * columns for _ in range(rows)]  # згасання за секунду
        self.glow = [[None] * columns for _ in range(rows)]  # колір голови
        self.drops = [None] * columns
        self.lit = []  # клітинки з головою — щоб згасити їх наступного кадру

    def update(self, dt):
        self._fade_trails(dt)
        self._move_drops(dt)
        self._flicker(dt)

    def _fade_trails(self, dt):
        """Плавно гасить усі намальовані символи."""
        for row in range(self.rows):
            bright_row = self.bright[row]
            fade_row = self.fade[row]
            for column in range(self.columns):
                level = bright_row[column]
                if level > 0.0:
                    level -= fade_row[column] * dt
                    bright_row[column] = level if level > 0.0 else 0.0

    def _move_drops(self, dt):
        """Просуває краплі, малює нові символи й підсвічує голови."""
        for row, column in self.lit:
            self.glow[row][column] = None
        self.lit.clear()

        last_row = self.rows - 1
        for column, drop in enumerate(self.drops):
            if drop is None:
                if random.random() < DROPS_PER_SEC * dt:
                    self.drops[column] = Drop()
                continue

            drop.y += drop.speed * dt
            head = int(drop.y)

            # Клітинки, які голова проминула за цей кадр
            painted = min(head, last_row)
            for row in range(drop.painted + 1, painted + 1):
                # У клітинку приходить той самий символ, який у ній уже
                # світився, — тому глиф не «підміняється» на льоту.
                self.chars[row][column] = (
                    drop.char if row == painted else random.choice(CHARS)
                )
                self.bright[row][column] = 1.0
                self.fade[row][column] = drop.fade
            if painted > drop.painted:
                drop.char = random.choice(CHARS)
                drop.painted = painted

            if head > last_row:  # голова пішла за край — хвіст догасне сам
                self.drops[column] = None
                continue

            # Голова стоїть між двома клітинками: частку entering вона вже
            # зайшла в наступну, частку (1 - entering) лишає в поточній.
            entering = drop.y - head
            self._light(head, column, HEAD_PALETTE[round((1.0 - entering) * GLOW_STEPS)])
            if head < last_row:
                if self.bright[head + 1][column] <= 0.0:
                    self.chars[head + 1][column] = drop.char
                self._light(head + 1, column, LEAD_PALETTE[round(entering * GLOW_STEPS)])

    def _light(self, row, column, color):
        self.glow[row][column] = color
        self.lit.append((row, column))

    def _flicker(self, dt):
        """Змінює символи в частині вже намальованих клітинок."""
        expected = self.columns * FLICKER_PER_SEC * dt
        for _ in range(int(expected) + (random.random() < expected % 1.0)):
            row = random.randrange(self.rows)
            column = random.randrange(self.columns)
            if self.bright[row][column] > 0.0 and self.glow[row][column] is None:
                self.chars[row][column] = random.choice(CHARS)

    def render(self):
        """Збирає кадр одним рядком: колір дописуємо лише коли він змінився."""
        frame = [HOME]
        append = frame.append
        shade_last = SHADES - 1
        previous = None
        for row in range(self.rows):
            if row:
                append("\n")
            chars_row = self.chars[row]
            bright_row = self.bright[row]
            glow_row = self.glow[row]
            for column in range(self.columns):
                color = glow_row[column]
                if color is None:
                    level = bright_row[column]
                    if level <= 0.0:
                        append(" ")
                        continue
                    color = TRAIL_PALETTE[int(level * shade_last)]
                if color != previous:
                    append(color)
                    previous = color
                append(chars_row[column])
        append(RESET)
        return "".join(frame)


def main():
    if os.name == "nt":
        os.system("")  # вмикає обробку ANSI-кодів у cmd.exe

    rain = Rain(*terminal_size())
    write = sys.stdout.write
    frame_time = 1.0 / FPS
    clock = time.perf_counter()

    write(ENTER_SCREEN)
    try:
        while True:
            started = time.perf_counter()
            # Рахуємо справжній час кадру, тому темп не збивається,
            # якщо система пригальмувала.
            dt = min(started - clock, 0.25)
            clock = started

            size = terminal_size()
            if size != (rain.columns, rain.rows):
                rain.resize(*size)
                write(CLEAR)

            rain.update(dt)
            write(rain.render())
            sys.stdout.flush()

            pause = frame_time - (time.perf_counter() - started)
            if pause > 0:
                time.sleep(pause)
    except KeyboardInterrupt:
        pass
    finally:
        # Термінал відновлюємо завжди, навіть якщо впала помилка
        write(EXIT_SCREEN)
        sys.stdout.flush()
        print("Програму зупинено.")


if __name__ == "__main__":
    main()
