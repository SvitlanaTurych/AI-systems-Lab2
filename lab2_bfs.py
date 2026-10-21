import sys
from PyQt5.QtWidgets import QApplication

from main_window import SearchVisualization


def main():
    app = QApplication(sys.argv)
    window = SearchVisualization()
    window.show()
    sys.exit(app.exec_())


if __name__ == "__main__":
    main()