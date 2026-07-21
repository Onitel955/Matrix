import random
import os
import time
import shutil

# --- КОНСТАНТИ ---
# Набір символів, що імітує код з "Матриці"
LATIN_AND_NUMS = "0123456789ABCDEFGHIJKLMNOPQRSTUVWXYZ"
HALF_WIDTH_KATAKANA = "ﾊﾐﾋｰｳｼﾅﾓﾆｻﾜﾂｵﾘｱﾎﾃﾏｹﾒｴｶｷﾑﾕﾗｾﾈｽﾀﾇﾍｦｲｸｺｿﾁﾄﾉﾌﾔﾖﾙﾚﾛﾝ"
KATAKANA = "アァカサタナハマヤャラワガザダバパイィキシチニヒミリヰギジヂビピウゥクスツヌフムユュルグズヅブプエェケセテネヘメレヱゲゼデベペオォコソトノホモヨョロヲゴゾドボポヴッン"
CHARS = LATIN_AND_NUMS + KATAKANA + HALF_WIDTH_KATAKANA

# ANSI коди кольорів
COLOR_BRIGHT_WHITE = "\033[97m"
COLOR_GREEN = "\033[32m"
COLOR_DARK_GREEN = "\033[90m" # Яскраво-чорний, виглядає як темний
COLOR_RESET = "\033[0m"


def matrix_effect():
    # # Отримуємо розмір терміналу (автоматично)
    # columns, rows = shutil.get_terminal_size()
    # Встановлюємо фіксований розмір (наприклад, 120 стовпців, 40 рядків)
    columns, rows = 120, 40

    # Для кожного стовпця відстежуємо позицію "краплі" та її довжину
    # -1 означає, що крапля неактивна
    drops = [{'y': -1, 'len': 0} for _ in range(columns)]

    # Очищуємо термінал перед початком
    os.system('cls' if os.name == 'nt' else 'clear')

    # Сховати курсор
    print("\033[?25l", end="")
    # Створюємо початковий порожній екран
    screen = [[' ' for _ in range(columns)] for _ in range(rows)]

    try:
        while True:
            # 1. Згасання існуючих символів
            for y in range(rows):
                for x in range(columns):
                    if screen[y][x] != ' ':
                        # Змінюємо колір або робимо пробілом для ефекту згасання
                        if screen[y][x].startswith(COLOR_BRIGHT_WHITE):
                            char = screen[y][x][-len(COLOR_RESET)-1]
                            screen[y][x] = f"{COLOR_GREEN}{char}{COLOR_RESET}"
                        elif screen[y][x].startswith(COLOR_GREEN):
                            char = screen[y][x][-len(COLOR_RESET)-1]
                            screen[y][x] = f"{COLOR_DARK_GREEN}{char}{COLOR_RESET}"
                        else:
                            screen[y][x] = ' '

            # 2. Рух та створення нових крапель
            for x in range(columns):
                if drops[x]['y'] == -1: # Якщо крапля неактивна
                    if random.random() > 0.975: # Створюємо нову з певною ймовірністю
                        drops[x]['y'] = 0
                        drops[x]['len'] = random.randint(5, rows - 5)
                else:
                    y = drops[x]['y']
                    if y < rows:
                        screen[y][x] = f"{COLOR_BRIGHT_WHITE}{random.choice(CHARS)}{COLOR_RESET}"
                    
                    drops[x]['y'] += 1
                    # Якщо крапля пройшла свою довжину, робимо її неактивною
                    if drops[x]['y'] >= drops[x]['len']:
                        drops[x] = {'y': -1, 'len': 0}

            # 3. Виводимо кадр на екран
            output = "\033[H" + "\n".join("".join(row) for row in screen)
            print(output, end="")
            time.sleep(0.15)

    except KeyboardInterrupt:
        # Скидання налаштувань терміналу при виході
        os.system('cls' if os.name == 'nt' else 'clear') # Очищуємо термінал
        print(f"\033[?25h{COLOR_RESET}", end="") # Повертаємо курсор і скидаємо колір
        print("\nПрограму зупинено.")


if __name__ == "__main__":
    matrix_effect()