import sys
import random
import os
import json

# --- Безопасный импорт мультимедиа-компонентов для предотвращения сбоев ---
try:
    from PyQt6.QtMultimedia import QSoundEffect
    from PyQt6.QtCore import QUrl

    sound_class = QSoundEffect
    sound_url_class = QUrl
    sound_enabled = True
    print("PyQt6-Multimedia загружен успешно. Звук включен.")
except (ImportError, ModuleNotFoundError):
    print("ПРЕДУПРЕЖДЕНИЕ: PyQt6-Multimedia не найден или вызвал ошибку. Запуск без звука.")


    class DummySound:
        def __init__(self, *args, **kwargs): pass

        def setSource(self, *args, **kwargs): pass

        def setLoopCount(self, *args, **kwargs): pass

        def setVolume(self, *args, **kwargs): pass

        def play(self, *args, **kwargs): pass

        def stop(self, *args, **kwargs): pass

        def isPlaying(self, *args, **kwargs): return False


    sound_class = DummySound
    sound_url_class = None
    sound_enabled = False

from PyQt6.QtWidgets import (QApplication, QMainWindow, QWidget, QVBoxLayout,
                             QPushButton, QLabel, QStackedWidget, QSlider, QComboBox, QGridLayout)
from PyQt6.QtGui import QPainter, QColor, QPixmap, QFont
from PyQt6.QtCore import Qt, QTimer, QRect, pyqtSignal, QSize

# --- Глобальные константы ---
SCREEN_WIDTH = 800
SCREEN_HEIGHT = 700
FPS = 60
HIGHSCORE_FILE = 'highscores.json'

# --- Настройки ---
BASE_DIR = os.path.dirname(os.path.abspath(__file__))

LEVEL_SETTINGS = {
    'Легкий': {'enemy_speed_min': 4, 'enemy_speed_max': 7, 'spawn_rate': 70},
    'Средний': {'enemy_speed_min': 6, 'enemy_speed_max': 10, 'spawn_rate': 50},
    'Сложный': {'enemy_speed_min': 9, 'enemy_speed_max': 14, 'spawn_rate': 30}
}

GRAPHICS_SETTINGS = {'Низкое': 0.8, 'Среднее': 1.0, 'Высокое': 1.2}


# --- Вспомогательные классы ---
class Enemy:
    def __init__(self, image, level_conf):
        self.image = image
        self.rect = QRect(
            random.randint(120, SCREEN_WIDTH - 120 - self.image.width()),
            random.randint(-300, -150),
            self.image.width(),
            self.image.height()
        )
        self.speed_offset = random.uniform(level_conf['enemy_speed_min'], level_conf['enemy_speed_max'])


class GameWidget(QWidget):
    gameOver = pyqtSignal(int)

    def __init__(self, settings_manager):
        super().__init__()
        self.settings_manager = settings_manager
        self.setFocusPolicy(Qt.FocusPolicy.StrongFocus)
        self.load_assets()
        self.init_sounds()
        self.timer = QTimer(self)
        self.timer.timeout.connect(self.update_game)
        self.keys_pressed = set()

    def load_pixmap(self, path, base_size):
        quality_multiplier = GRAPHICS_SETTINGS[self.settings_manager.get_setting('graphics')]
        size = (int(base_size[0] * quality_multiplier), int(base_size[1] * quality_multiplier))
        full_path = os.path.join(BASE_DIR, path)
        if os.path.exists(full_path):
            pixmap = QPixmap(full_path)
            return pixmap.scaled(QSize(*size), Qt.AspectRatioMode.KeepAspectRatio,
                                 Qt.TransformationMode.SmoothTransformation)
        else:
            print(f"Warning: Asset not found at {full_path}. Using fallback color.")
            pixmap = QPixmap(QSize(*size));
            pixmap.fill(QColor("purple"));
            return pixmap

    def load_assets(self):
        self.player_image = self.load_pixmap(os.path.join('assets', 'images', 'player_car.png'), (50, 100))
        self.enemy_images = [
            self.load_pixmap(os.path.join('assets', 'images', 'enemy_car_1.png'), (50, 100)),
            self.load_pixmap(os.path.join('assets', 'images', 'enemy_car_2.png'), (50, 100))
        ]
        self.road_image = self.load_pixmap(os.path.join('assets', 'images', 'road.png'), (SCREEN_WIDTH, SCREEN_HEIGHT))
        self.gas_pedal_icon = self.load_pixmap(os.path.join('assets', 'images', 'arrow_up.png'), (64, 64))
        self.brake_pedal_icon = self.load_pixmap(os.path.join('assets', 'images', 'arrow_down.png'), (64, 64))

    def init_sounds(self):
        self.sounds = {}
        if not sound_enabled:
            return

        sound_files = {
            'gas': os.path.join('assets', 'sounds', 'gas.wav'), 'brake': os.path.join('assets', 'sounds', 'brake.wav'),
            'honk': os.path.join('assets', 'sounds', 'honk.wav'), 'crash': os.path.join('assets', 'sounds', 'crash.wav')
        }
        for name, path in sound_files.items():
            full_path = os.path.join(BASE_DIR, path)
            if os.path.exists(full_path):
                sound = sound_class(self)
                sound.setSource(sound_url_class.fromLocalFile(full_path))
                self.sounds[name] = sound
            else:
                print(f"Warning: Sound not found at {full_path}");
                self.sounds[name] = None

        if self.sounds.get('gas'):
            # --- ОКОНЧАТЕЛЬНОЕ ИСПРАВЛЕНИЕ ---
            # Используем напрямую число -2 для бесконечного повтора
            self.sounds['gas'].setLoopCount(-2)

    def play_sound(self, name, stop=False):
        sound = self.sounds.get(name)
        if sound:
            volume = self.settings_manager.get_setting('sound_volume') / 100.0
            sound.setVolume(volume)
            if stop:
                sound.stop()
            elif not sound.isPlaying():
                sound.play()

    def start_game(self, level_name):
        self.load_assets();
        self.level_name = level_name
        self.current_level_settings = LEVEL_SETTINGS[level_name]
        self.game_running = True;
        self.score = 0

        self.player_vertical_speed = 0;
        self.acceleration = 0.5
        self.braking = 0.5;
        self.natural_deceleration = 0.98
        self.max_player_speed = 15;
        self.road_scroll_speed = 5

        self.player_rect = QRect((self.width() - self.player_image.width()) // 2,
                                 self.height() - self.player_image.height() - 20, self.player_image.width(),
                                 self.player_image.height())
        self.player_side_speed = 8;
        self.enemies = [];
        self.enemy_timer = 0;
        self.road_offset_y = 0
        self.keys_pressed.clear();
        self.timer.start(1000 // FPS);
        self.setFocus()

    def keyPressEvent(self, event):
        if not event.isAutoRepeat():
            self.keys_pressed.add(event.key())
            if event.key() == Qt.Key.Key_Space: self.play_sound('honk')

    def keyReleaseEvent(self, event):
        if not event.isAutoRepeat(): self.keys_pressed.discard(event.key())

    def update_game(self):
        if not self.game_running: return

        is_accelerating = False;
        is_braking = False

        if self.settings_manager.get_setting('accel_mode') == 'Педаль':
            if Qt.Key.Key_Up in self.keys_pressed:
                self.player_vertical_speed -= self.acceleration; is_accelerating = True
            elif Qt.Key.Key_Down in self.keys_pressed:
                self.player_vertical_speed += self.braking; is_braking = True
        else:
            self.player_vertical_speed = -5

        if not is_accelerating and not is_braking:
            self.player_vertical_speed *= self.natural_deceleration
            if abs(self.player_vertical_speed) < 0.1: self.player_vertical_speed = 0

        self.player_vertical_speed = max(-self.max_player_speed, min(self.player_vertical_speed, self.max_player_speed))
        self.player_rect.moveTop(self.player_rect.top() + int(self.player_vertical_speed))

        if self.player_rect.top() < 0: self.player_rect.moveTop(0); self.player_vertical_speed = 0
        if self.player_rect.bottom() > self.height(): self.player_rect.moveBottom(
            self.height()); self.player_vertical_speed = 0

        if is_accelerating:
            self.play_sound('gas');
        else:
            self.play_sound('gas', stop=True)
        if is_braking:
            self.play_sound('brake')
        else:
            self.play_sound('brake', stop=True)

        if (Qt.Key.Key_Left in self.keys_pressed) and self.player_rect.left() > 110: self.player_rect.moveLeft(
            self.player_rect.left() - self.player_side_speed)
        if (
                Qt.Key.Key_Right in self.keys_pressed) and self.player_rect.right() < self.width() - 110: self.player_rect.moveRight(
            self.player_rect.right() + self.player_side_speed)

        self.road_offset_y = (self.road_offset_y + self.road_scroll_speed) % self.height()
        if self.player_vertical_speed < 0: self.score += 1

        self.enemy_timer += 1
        if self.enemy_timer > self.current_level_settings['spawn_rate'] and len(self.enemies) < 5:
            self.enemy_timer = 0;
            self.enemies.append(Enemy(random.choice(self.enemy_images), self.current_level_settings))

        for enemy in self.enemies[:]:
            enemy.rect.moveTop(enemy.rect.top() + int(enemy.speed_offset))
            if enemy.rect.bottom() < self.player_rect.top() and not hasattr(enemy, 'overtaken'):
                self.score += 150;
                enemy.overtaken = True
            if enemy.rect.top() > self.height() + 100:
                if enemy in self.enemies: self.enemies.remove(enemy)
            if self.player_rect.intersects(enemy.rect): self.end_game(); return
        self.update()

    def end_game(self):
        self.game_running = False;
        self.timer.stop();
        self.play_sound('gas', stop=True)
        self.play_sound('brake', stop=True);
        self.play_sound('crash')
        self.settings_manager.check_and_save_score(self.score);
        self.gameOver.emit(self.score)

    def paintEvent(self, event):
        painter = QPainter(self)
        painter.drawPixmap(0, self.road_offset_y, self.road_image)
        painter.drawPixmap(0, self.road_offset_y - self.height(), self.road_image)
        for enemy in self.enemies: painter.drawPixmap(enemy.rect, enemy.image)
        painter.drawPixmap(self.player_rect, self.player_image)
        self.draw_hud(painter);
        painter.end()

    def draw_hud(self, painter):
        painter.setPen(QColor("white"));
        painter.setFont(QFont("Arial", 16, QFont.Weight.Bold))
        hud_bg_rect = QRect(self.width() - 220, 10, 210, 100)
        painter.setBrush(QColor(0, 0, 0, 150));
        painter.drawRect(hud_bg_rect)
        speed_kmh = abs(self.player_vertical_speed * 10)
        scores = self.settings_manager.load_highscores();
        top_score = scores[0]['score'] if scores else 0
        painter.drawText(hud_bg_rect.adjusted(10, 5, 0, 0), Qt.AlignmentFlag.AlignTop | Qt.AlignmentFlag.AlignLeft,
                         f"Скорость: {speed_kmh:.0f} км/ч")
        painter.drawText(hud_bg_rect.adjusted(10, 35, 0, 0), Qt.AlignmentFlag.AlignTop | Qt.AlignmentFlag.AlignLeft,
                         f"Рекорд: {top_score}")
        painter.drawText(hud_bg_rect.adjusted(10, 65, 0, 0), Qt.AlignmentFlag.AlignTop | Qt.AlignmentFlag.AlignLeft,
                         f"Очки: {self.score}")
        if self.settings_manager.get_setting('accel_mode') == 'Педаль':
            gas_rect = QRect(self.width() - 80, self.height() - 160, 64, 64)
            painter.setOpacity(0.5 if Qt.Key.Key_Up not in self.keys_pressed else 1.0);
            painter.drawPixmap(gas_rect, self.gas_pedal_icon)
            brake_rect = QRect(self.width() - 80, self.height() - 80, 64, 64)
            painter.setOpacity(0.5 if Qt.Key.Key_Down not in self.keys_pressed else 1.0);
            painter.drawPixmap(brake_rect, self.brake_pedal_icon)
            painter.setOpacity(1.0)


# --- Остальные классы (SettingsManager, Menus, MainWindow) остаются без изменений ---
class SettingsManager:
    def __init__(self):
        self.settings = {'sound_volume': 50, 'graphics': 'Среднее', 'accel_mode': 'Педаль'}

    def get_setting(self, key):
        return self.settings.get(key)

    def set_setting(self, key, value):
        self.settings[key] = value

    def load_highscores(self):
        try:
            with open(os.path.join(BASE_DIR, HIGHSCORE_FILE), 'r') as f:
                return json.load(f)
        except (FileNotFoundError, json.JSONDecodeError):
            return []

    def save_highscores(self, scores):
        with open(os.path.join(BASE_DIR, HIGHSCORE_FILE), 'w') as f: json.dump(scores, f, indent=4)

    def check_and_save_score(self, score):
        scores = self.load_highscores();
        scores.append({'score': score})
        scores = sorted(scores, key=lambda x: x['score'], reverse=True);
        self.save_highscores(scores[:10])


class BaseMenuWidget(QWidget):
    def __init__(self):
        super().__init__();
        self.layout = QVBoxLayout(self)
        self.layout.setAlignment(Qt.AlignmentFlag.AlignCenter);
        self.layout.setSpacing(20)
        self.setStyleSheet("""QWidget { background-color: #2c3e50; }
            QPushButton { background-color: #3498db; color: white; font-size: 24px; padding: 15px; border-radius: 10px; border: 2px solid #2980b9; min-width: 300px;}
            QPushButton:hover { background-color: #5dade2; }
            QLabel { color: white; font-size: 48px; font-weight: bold; background-color: transparent;}
            QSlider::groove:horizontal { border: 1px solid #bbb; background: white; height: 10px; border-radius: 4px; }
            QSlider::handle:horizontal { background: #3498db; border: 1px solid #2980b9; width: 18px; margin: -2px 0; border-radius: 9px; }
            QComboBox { font-size: 18px; padding: 5px; }""")


class MainMenuWidget(BaseMenuWidget):
    showLevelSelect, showSettings, showHighScores = pyqtSignal(), pyqtSignal(), pyqtSignal()

    def __init__(self):
        super().__init__();
        title = QLabel("2D Traffic Racer")
        start_button, settings_button = QPushButton("Начать игру"), QPushButton("Настройки")
        highscores_button, exit_button = QPushButton("Рекорды"), QPushButton("Выход")
        start_button.clicked.connect(self.showLevelSelect.emit);
        settings_button.clicked.connect(self.showSettings.emit)
        highscores_button.clicked.connect(self.showHighScores.emit);
        exit_button.clicked.connect(QApplication.instance().quit)
        self.layout.addWidget(title, alignment=Qt.AlignmentFlag.AlignCenter);
        self.layout.addWidget(start_button)
        self.layout.addWidget(settings_button);
        self.layout.addWidget(highscores_button);
        self.layout.addWidget(exit_button)


class SettingsWidget(BaseMenuWidget):
    backToMenu = pyqtSignal()

    def __init__(self, settings_manager):
        super().__init__();
        self.settings_manager = settings_manager;
        title = QLabel("Настройки")
        title.setStyleSheet("font-size: 40px;");
        self.layout.addWidget(title, alignment=Qt.AlignmentFlag.AlignCenter)
        grid_layout = QGridLayout();
        grid_layout.setSpacing(15)
        sound_label = QLabel("Громкость");
        sound_label.setStyleSheet("font-size: 20px; font-weight: normal;")
        self.sound_slider = QSlider(Qt.Orientation.Horizontal);
        self.sound_slider.setRange(0, 100)
        grid_layout.addWidget(sound_label, 0, 0);
        grid_layout.addWidget(self.sound_slider, 0, 1)
        graphics_label = QLabel("Графика");
        graphics_label.setStyleSheet("font-size: 20px; font-weight: normal;")
        self.graphics_combo = QComboBox();
        self.graphics_combo.addItems(GRAPHICS_SETTINGS.keys())
        grid_layout.addWidget(graphics_label, 1, 0);
        grid_layout.addWidget(self.graphics_combo, 1, 1)
        accel_label = QLabel("Ускорение");
        accel_label.setStyleSheet("font-size: 20px; font-weight: normal;")
        self.accel_combo = QComboBox();
        self.accel_combo.addItems(['Педаль', 'Авто'])
        grid_layout.addWidget(accel_label, 2, 0);
        grid_layout.addWidget(self.accel_combo, 2, 1)
        self.layout.addLayout(grid_layout);
        back_button = QPushButton("Назад");
        back_button.clicked.connect(self.save_and_exit)
        self.layout.addWidget(back_button, alignment=Qt.AlignmentFlag.AlignCenter)

    def showEvent(self, event):
        self.sound_slider.setValue(self.settings_manager.get_setting('sound_volume'))
        self.graphics_combo.setCurrentText(self.settings_manager.get_setting('graphics'))
        self.accel_combo.setCurrentText(self.settings_manager.get_setting('accel_mode'));
        super().showEvent(event)

    def save_and_exit(self):
        self.settings_manager.set_setting('sound_volume', self.sound_slider.value())
        self.settings_manager.set_setting('graphics', self.graphics_combo.currentText())
        self.settings_manager.set_setting('accel_mode', self.accel_combo.currentText());
        self.backToMenu.emit()


class HighScoresWidget(BaseMenuWidget):
    backToMenu = pyqtSignal()

    def __init__(self, settings_manager):
        super().__init__();
        self.settings_manager = settings_manager
        title = QLabel("Таблица рекордов");
        title.setStyleSheet("font-size: 40px;");
        self.layout.addWidget(title, alignment=Qt.AlignmentFlag.AlignCenter)
        self.scores_layout = QVBoxLayout();
        self.layout.addLayout(self.scores_layout)
        back_button = QPushButton("Назад");
        back_button.clicked.connect(self.backToMenu.emit)
        self.layout.addWidget(back_button, alignment=Qt.AlignmentFlag.AlignCenter)

    def showEvent(self, event):
        for i in reversed(range(self.scores_layout.count())): self.scores_layout.itemAt(i).widget().setParent(None)
        scores = self.settings_manager.load_highscores()
        if not scores:
            no_scores_label = QLabel("Рекордов пока нет!"); no_scores_label.setStyleSheet(
                "font-size: 24px; font-weight: normal;"); self.scores_layout.addWidget(no_scores_label,
                                                                                       alignment=Qt.AlignmentFlag.AlignCenter)
        else:
            for i, record in enumerate(scores): score_label = QLabel(
                f"{i + 1}. {record['score']} очков"); score_label.setStyleSheet(
                "font-size: 22px; font-weight: normal;"); self.scores_layout.addWidget(score_label,
                                                                                       alignment=Qt.AlignmentFlag.AlignCenter)
        super().showEvent(event)


class LevelSelectWidget(BaseMenuWidget):
    levelSelected = pyqtSignal(str)

    def __init__(self):
        super().__init__();
        title = QLabel("Выберите уровень");
        self.layout.addWidget(title, alignment=Qt.AlignmentFlag.AlignCenter)
        for level_name in LEVEL_SETTINGS.keys(): btn = QPushButton(level_name); btn.clicked.connect(
            lambda checked, name=level_name: self.levelSelected.emit(name)); self.layout.addWidget(btn)


class GameOverWidget(BaseMenuWidget):
    restartGame, backToMenu = pyqtSignal(), pyqtSignal()

    def __init__(self):
        super().__init__();
        self.title = QLabel("Игра окончена");
        self.score_label = QLabel();
        self.score_label.setStyleSheet("font-size: 32px; font-weight: normal;")
        restart_button, menu_button = QPushButton("Играть снова"), QPushButton("Главное меню")
        restart_button.clicked.connect(self.restartGame.emit);
        menu_button.clicked.connect(self.backToMenu.emit)
        self.layout.addWidget(self.title, alignment=Qt.AlignmentFlag.AlignCenter);
        self.layout.addWidget(self.score_label, alignment=Qt.AlignmentFlag.AlignCenter)
        self.layout.addWidget(restart_button);
        self.layout.addWidget(menu_button)

    def set_score(self, score): self.score_label.setText(f"Ваш итоговый счет: {score}")


class MainWindow(QMainWindow):
    def __init__(self):
        super().__init__();
        self.setWindowTitle("2D Traffic Racer на PyQt6");
        self.setFixedSize(SCREEN_WIDTH, SCREEN_HEIGHT)
        self.settings_manager = SettingsManager();
        self.stacked_widget = QStackedWidget();
        self.setCentralWidget(self.stacked_widget)
        self.main_menu = MainMenuWidget();
        self.settings_widget = SettingsWidget(self.settings_manager)
        self.highscores_widget = HighScoresWidget(self.settings_manager);
        self.level_select = LevelSelectWidget()
        self.game_widget = GameWidget(self.settings_manager);
        self.game_over_widget = GameOverWidget()
        widgets = [self.main_menu, self.settings_widget, self.highscores_widget, self.level_select, self.game_widget,
                   self.game_over_widget]
        for w in widgets: self.stacked_widget.addWidget(w)
        self.main_menu.showLevelSelect.connect(self.show_level_select);
        self.main_menu.showSettings.connect(self.show_settings);
        self.main_menu.showHighScores.connect(self.show_highscores)
        self.settings_widget.backToMenu.connect(self.show_main_menu);
        self.highscores_widget.backToMenu.connect(self.show_main_menu)
        self.level_select.levelSelected.connect(self.start_game);
        self.game_widget.gameOver.connect(self.show_game_over)
        self.game_over_widget.restartGame.connect(self.show_level_select);
        self.game_over_widget.backToMenu.connect(self.show_main_menu)
        self.show_main_menu()

    def show_main_menu(self): self.stacked_widget.setCurrentWidget(self.main_menu)

    def show_level_select(self): self.stacked_widget.setCurrentWidget(self.level_select)

    def show_settings(self): self.stacked_widget.setCurrentWidget(self.settings_widget)

    def show_highscores(self): self.stacked_widget.setCurrentWidget(self.highscores_widget)

    def start_game(self, level_name): self.game_widget.start_game(level_name); self.stacked_widget.setCurrentWidget(
        self.game_widget)

    def show_game_over(self, score): self.game_over_widget.set_score(score); self.stacked_widget.setCurrentWidget(
        self.game_over_widget)


if __name__ == '__main__':
    app = QApplication(sys.argv)
    window = MainWindow()
    window.show()
    sys.exit(app.exec())