import os
import random
import shutil
import sys
import time

# --- НАБІР СИМВОЛІВ ---
# У фільмі використана саме напівширинна катакана: вона моноширинна,
# тому сітка не "розповзається". Повноширинні (アカサ...) займають
# 2 стовпці в терміналі й ламають вирівнювання — тому їх не беремо.
HALF_WIDTH_KATAKANA = "ﾊﾐﾋｰｳｼﾅﾓﾆｻﾜﾂｵﾘｱﾎﾃﾏｹﾒｴｶｷﾑﾕﾗｾﾈｽﾀﾇﾍｦｲｸｺｿﾁﾄﾉﾌﾔﾖﾙﾚﾛﾝ"
DIGITS_AND_SIGNS = "0123456789Z:.=*+-<>¦"
CHARS = HALF_WIDTH_KATAKANA * 3 + DIGITS_AND_SIGNS

# --- НАЛАШТУВАННЯ ЕФЕКТУ ---
FPS = 30                  # кадрів на секунду (плавність картинки)
DROP_SPEED = (0.16, 0.5)  # клітинок за кадр (різна швидкість = "живий" дощ)
TRAIL_LEN = (8, 30)       # довжина хвоста в клітинках
SPAWN_CHANCE = 0.008      # шанс запустити нову краплю в порожньому стовпці
FLICKER_RATIO = 0.12      # частка ширини екрана, що мерехтить щокадру
FIXED_SIZE = None         # напр. (120, 40); None — брати розмір терміналу

# --- КОЛЬОРИ (ANSI 256) ---
COLOR_RESET = "\033[0m"
HEAD_COLOR = "\033[1;97m"  # яскраво-біла "голова" краплі
GREEN_RAMP = (
    "\033[38;5;194m",
    "\033[38;5;157m",
    "\033[38;5;120m",
    "\033[38;5;84m",
    "\033[38;5;48m",
    "\033[38;5;41m",
    "\033[38;5;35m",
    "\033[38;5;29m",
    "\033[38;5;23m",
    "\033[38;5;22m",
)

# --- КЕРУВАННЯ ТЕРМІНАЛОМ ---
ENTER_SCREEN = "\033[?1049h\033[?25l\033[?7l\033[2J"  # альт. екран, без курсора, без переносу
EXIT_SCREEN = "\033[?7h\033[?25h\033[?1049l" + COLOR_RESET


def get_size():
    """Розмір полотна — усе вікно терміналу (або FIXED_SIZE, якщо задано).

    Питаємо розмір напряму в терміналу через ioctl: shutil.get_terminal_size()
    спершу дивиться на COLUMNS/LINES, а вони в IDE-консолях і в tmux часто
    застарілі — через це кадр займав лише частину вікна.
    """
    if FIXED_SIZE:
        return FIXED_SIZE

    for stream in (sys.__stdout__, sys.__stderr__, sys.__stdin__):
        try:
            size = os.get_terminal_size(stream.fileno())
        except (OSError, ValueError, AttributeError):
            continue  # не термінал (перенаправлений вивід) — пробуємо наступний
        if size.columns > 0 and size.lines > 0:
            return max(size.columns, 20), max(size.lines, 10)

    # Резерв: змінні оточення, далі — 120x40
    columns, rows = shutil.get_terminal_size((120, 40))
    return max(columns, 20), max(rows, 10)


def new_drop():
    """Нова крапля: позиція голови, швидкість, довжина хвоста."""
    speed = random.uniform(*DROP_SPEED)
    # Хвіст задаємо в клітинках, а живе він у кадрах: чим повільніша
    # крапля, тим довше має гаснути слід, щоб довжина не залежала від швидкості
    return {
        "y": 0.0,
        "last": -1,  # останній уже намальований рядок
        "speed": speed,
        "life": max(2, round(random.randint(*TRAIL_LEN) / speed)),
    }


def matrix_effect():
    columns, rows = get_size()
    # chars — символ у клітинці, age — скільки кадрів він живе,
    # life — через скільки кадрів згасне остаточно (-1 в age = порожньо)
    chars = [[" "] * columns for _ in range(rows)]
    age = [[-1] * columns for _ in range(rows)]
    life = [[1] * columns for _ in range(rows)]
    drops = [None] * columns

    frame_time = 1.0 / FPS
    ramp_last = len(GREEN_RAMP) - 1
    write = sys.stdout.write

    write(ENTER_SCREEN)
    try:
        while True:
            frame_start = time.perf_counter()

            # 0. Реакція на зміну розміру вікна
            if (columns, rows) != get_size():
                columns, rows = get_size()
                chars = [[" "] * columns for _ in range(rows)]
                age = [[-1] * columns for _ in range(rows)]
                life = [[1] * columns for _ in range(rows)]
                drops = [None] * columns
                write("\033[2J")

            # 1. Згасання: кожна клітинка живе стільки кадрів,
            #    скільки задала довжина хвоста своєї краплі
            for y in range(rows):
                age_row = age[y]
                life_row = life[y]
                for x in range(columns):
                    a = age_row[x]
                    if a >= 0:
                        a += 1
                        age_row[x] = a if a <= life_row[x] else -1

            # 2. Рух крапель і поява нових
            for x in range(columns):
                drop = drops[x]
                if drop is None:
                    if random.random() < SPAWN_CHANCE:
                        drops[x] = new_drop()
                    continue

                drop["y"] += drop["speed"]
                head = int(drop["y"])
                # Малюємо всі клітинки, які голова проминула за цей кадр
                for y in range(drop["last"] + 1, min(head, rows - 1) + 1):
                    chars[y][x] = random.choice(CHARS)
                    age[y][x] = 0
                    life[y][x] = drop["life"]
                drop["last"] = min(head, rows - 1)
                # Голова лишається білою, поки не зрушить далі:
                # при швидкості < 1 вона стоїть на клітинці кілька кадрів
                age[drop["last"]][x] = 0

                if head >= rows:  # голова пішла за край — хвіст догасне сам
                    drops[x] = None

            # 3. Мерехтіння: частина видимих символів змінюється на льоту
            for _ in range(int(columns * FLICKER_RATIO)):
                fx = random.randrange(columns)
                fy = random.randrange(rows)
                if age[fy][fx] > 0:
                    chars[fy][fx] = random.choice(CHARS)

            # 4. Складаємо кадр одним рядком; колір пишемо лише коли він змінився
            out = ["\033[H"]
            append = out.append
            prev_color = None
            for y in range(rows):
                if y:
                    append("\n")
                age_row = age[y]
                life_row = life[y]
                char_row = chars[y]
                for x in range(columns):
                    a = age_row[x]
                    if a < 0:
                        append(" ")
                        continue
                    if a == 0:
                        color = HEAD_COLOR
                    else:
                        idx = a * ramp_last // life_row[x]
                        color = GREEN_RAMP[idx if idx < ramp_last else ramp_last]
                    if color != prev_color:
                        append(color)
                        prev_color = color
                    append(char_row[x])
            append(COLOR_RESET)

            write("".join(out))
            sys.stdout.flush()

            # 5. Тримаємо стабільний FPS з поправкою на час рендера
            delay = frame_time - (time.perf_counter() - frame_start)
            if delay > 0:
                time.sleep(delay)

    except KeyboardInterrupt:
        pass
    finally:
        # Термінал відновлюємо завжди, навіть якщо впала помилка
        write(EXIT_SCREEN)
        sys.stdout.flush()
        print("Програму зупинено.")


if __name__ == "__main__":
    if os.name == "nt":
        os.system("")  # вмикає обробку ANSI-кодів у cmd.exe
    matrix_effect()
