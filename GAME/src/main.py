import sys
import random
import os
from PyQt6.QtWidgets import QApplication, QMainWindow, QWidget, QVBoxLayout, QPushButton, QLabel, QStackedWidget
from PyQt6.QtGui import QPainter, QColor, QBrush, QPen, QPixmap, QFont
from PyQt6.QtCore import Qt, QTimer, QRect, pyqtSignal, QSize

SCREEN_WIDTH = 800
SCREEN_HEIGHT = 700
FPS = 60


LEVEL_SETTINGS = {
    'Легкий': {'speed_min': 5, 'speed_max': 8, 'spawn_rate': 60},
    'Средний': {'speed_min': 8, 'speed_max': 12, 'spawn_rate': 40},
    'Сложный': {'speed_min': 12, 'speed_max': 18, 'spawn_rate': 25}
}



class Enemy:
    def __init__(self, image, level_conf):
        self.image = image
        self.rect = QRect(
            random.randint(50, SCREEN_WIDTH - 50 - self.image.width()),
            random.randint(-200, -100),
            self.image.width(),
            self.image.height()
        )
        self.speed = random.randint(level_conf['speed_min'], level_conf['speed_max'])

    def update(self):
        self.rect.moveTop(self.rect.top() + self.speed)



class GameWidget(QWidget):
    gameOver = pyqtSignal(int)

    def __init__(self):
        super().__init__()
        self.setFocusPolicy(Qt.FocusPolicy.StrongFocus)
        self.load_assets()

        self.timer = QTimer()
        self.timer.timeout.connect(self.update_game)
        self.keys_pressed = set()

    def load_assets(self):
        self.player_image = self.load_pixmap(os.path.join('assets', 'images', 'player_car.png'), (50, 100),
                                             QColor("blue"))
        self.enemy_images = [
            self.load_pixmap(os.path.join('assets', 'images', 'enemy_car_1.png'), (50, 100), QColor("red")),
            self.load_pixmap(os.path.join('assets', 'images', 'enemy_car_2.png'), (50, 100), QColor("green"))
        ]
        self.road_image = self.load_pixmap(os.path.join('assets', 'images', 'road.png'), (SCREEN_WIDTH, SCREEN_HEIGHT),
                                           QColor(100, 100, 100))

    def load_pixmap(self, path, size, fallback_color):
        if os.path.exists(path):
            pixmap = QPixmap(path)
            return pixmap.scaled(QSize(*size), Qt.AspectRatioMode.KeepAspectRatio,
                                 Qt.TransformationMode.SmoothTransformation)
        else:
            print(f"Warning: Asset not found at {path}. Using fallback color.")
            pixmap = QPixmap(QSize(*size))
            pixmap.fill(fallback_color)
            return pixmap

    def start_game(self, level_name):
    
        self.level_name = level_name
        self.current_level_settings = LEVEL_SETTINGS[level_name]
        self.score = 0
        self.game_running = True

        self.player_rect = QRect(
            (self.width() - self.player_image.width()) // 2,
            self.height() - self.player_image.height() - 20,
            self.player_image.width(),
            self.player_image.height()
        )
        self.player_speed = 8

        self.enemies = []
        self.enemy_timer = 0
        self.road_offset_y = 0

        self.keys_pressed.clear()
        self.timer.start(1000 // FPS)
        self.setFocus()

    def keyPressEvent(self, event):
        self.keys_pressed.add(event.key())

    def keyReleaseEvent(self, event):
        self.keys_pressed.discard(event.key())

    def update_game(self):
        if not self.game_running:
            return

        # Движение игрока
        if (Qt.Key.Key_Left in self.keys_pressed or Qt.Key.Key_A in self.keys_pressed) and self.player_rect.left() > 0:
            self.player_rect.moveLeft(self.player_rect.left() - self.player_speed)
        if (
                Qt.Key.Key_Right in self.keys_pressed or Qt.Key.Key_D in self.keys_pressed) and self.player_rect.right() < self.width():
            self.player_rect.moveRight(self.player_rect.right() + self.player_speed)

        # Прокрутка дороги
        self.road_offset_y = (self.road_offset_y + self.current_level_settings['speed_min']) % self.height()

        # Создание и обновление врагов
        self.enemy_timer += 1
        if self.enemy_timer > self.current_level_settings['spawn_rate']:
            self.enemy_timer = 0
            enemy_image = random.choice(self.enemy_images)
            self.enemies.append(Enemy(enemy_image, self.current_level_settings))

        for enemy in self.enemies[:]:
            enemy.update()
            if enemy.rect.top() > self.height():
                self.enemies.remove(enemy)
                self.score += 1
            if self.player_rect.intersects(enemy.rect):
                self.end_game()
                return

        self.update()  # Запрос на перерисовку виджета

    def end_game(self):
        self.game_running = False
        self.timer.stop()
        self.gameOver.emit(self.score)

    def paintEvent(self, event):
        painter = QPainter(self)

        # Рисуем дорогу (2 копии для бесшовной прокрутки)
        painter.drawPixmap(0, self.road_offset_y, self.road_image)
        painter.drawPixmap(0, self.road_offset_y - self.height(), self.road_image)

        # Рисуем игрока
        painter.drawPixmap(self.player_rect, self.player_image)

        # Рисуем врагов
        for enemy in self.enemies:
            painter.drawPixmap(enemy.rect, enemy.image)

        # Рисуем интерфейс (счет, уровень)
        painter.setPen(QColor("white"))
        painter.setFont(QFont("Arial", 16, QFont.Weight.Bold))
        painter.drawText(20, 40, f"Счет: {self.score}")
        painter.drawText(self.width() - 150, 40, f"Уровень: {self.level_name}")

        painter.end()


# --- Классы для виджетов меню ---
class BaseMenuWidget(QWidget):
    def __init__(self):
        super().__init__()
        self.layout = QVBoxLayout(self)
        self.layout.setAlignment(Qt.AlignmentFlag.AlignCenter)
        self.layout.setSpacing(20)
        self.setStyleSheet("""
            BaseMenuWidget { background-color: #2c3e50; }
            QPushButton { 
                background-color: #3498db; color: white; font-size: 24px; 
                padding: 15px; border-radius: 10px; border: 2px solid #2980b9;
            }
            QPushButton:hover { background-color: #5dade2; }
            QLabel { color: white; font-size: 48px; font-weight: bold; }
        """)


class MainMenuWidget(BaseMenuWidget):
    startGame = pyqtSignal()

    def __init__(self):
        super().__init__()
        title = QLabel("2D Traffic Racer")
        start_button = QPushButton("Начать игру")
        exit_button = QPushButton("Выход")

        start_button.clicked.connect(self.startGame.emit)
        exit_button.clicked.connect(QApplication.instance().quit)

        self.layout.addWidget(title, alignment=Qt.AlignmentFlag.AlignCenter)
        self.layout.addWidget(start_button)
        self.layout.addWidget(exit_button)


class LevelSelectWidget(BaseMenuWidget):
    levelSelected = pyqtSignal(str)

    def __init__(self):
        super().__init__()
        title = QLabel("Выберите уровень")
        self.layout.addWidget(title, alignment=Qt.AlignmentFlag.AlignCenter)

        for level_name in LEVEL_SETTINGS.keys():
            btn = QPushButton(level_name)
            btn.clicked.connect(lambda checked, name=level_name: self.levelSelected.emit(name))
            self.layout.addWidget(btn)


class GameOverWidget(BaseMenuWidget):
    restartGame = pyqtSignal()
    backToMenu = pyqtSignal()

    def __init__(self):
        super().__init__()
        self.title = QLabel("Игра окончена")
        self.score_label = QLabel()
        self.score_label.setStyleSheet("font-size: 32px; font-weight: normal;")
        restart_button = QPushButton("Играть снова")
        menu_button = QPushButton("Главное меню")

        restart_button.clicked.connect(self.restartGame.emit)
        menu_button.clicked.connect(self.backToMenu.emit)

        self.layout.addWidget(self.title, alignment=Qt.AlignmentFlag.AlignCenter)
        self.layout.addWidget(self.score_label, alignment=Qt.AlignmentFlag.AlignCenter)
        self.layout.addWidget(restart_button)
        self.layout.addWidget(menu_button)

    def set_score(self, score):
        self.score_label.setText(f"Ваш итоговый счет: {score}")


# --- Главное окно приложения ---
class MainWindow(QMainWindow):
    def __init__(self):
        super().__init__()
        self.setWindowTitle("2D Traffic Racer на PyQt6")
        self.setFixedSize(SCREEN_WIDTH, SCREEN_HEIGHT)

        self.stacked_widget = QStackedWidget()
        self.setCentralWidget(self.stacked_widget)

        self.main_menu = MainMenuWidget()
        self.level_select = LevelSelectWidget()
        self.game_widget = GameWidget()
        self.game_over_widget = GameOverWidget()

        self.stacked_widget.addWidget(self.main_menu)
        self.stacked_widget.addWidget(self.level_select)
        self.stacked_widget.addWidget(self.game_widget)
        self.stacked_widget.addWidget(self.game_over_widget)

        # Соединяем сигналы и слоты для навигации по приложению
        self.main_menu.startGame.connect(self.show_level_select)
        self.level_select.levelSelected.connect(self.start_game)
        self.game_widget.gameOver.connect(self.show_game_over)
        self.game_over_widget.restartGame.connect(self.show_level_select)
        self.game_over_widget.backToMenu.connect(self.show_main_menu)

        self.show_main_menu()

    def show_main_menu(self):
        self.stacked_widget.setCurrentWidget(self.main_menu)

    def show_level_select(self):
        self.stacked_widget.setCurrentWidget(self.level_select)

    def start_game(self, level_name):
        self.game_widget.start_game(level_name)
        self.stacked_widget.setCurrentWidget(self.game_widget)

    def show_game_over(self, score):
        self.game_over_widget.set_score(score)
        self.stacked_widget.setCurrentWidget(self.game_over_widget)


if __name__ == '__main__':
    app = QApplication(sys.argv)
    window = MainWindow()
    window.show()
    sys.exit(app.exec())