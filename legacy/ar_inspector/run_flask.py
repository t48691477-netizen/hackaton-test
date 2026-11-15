import sys
import socket
from pathlib import Path

# Предотвращаем задержки DNS резолва локального хоста на Windows
socket.gethostbyname_ex = lambda name: (name, [], ["127.0.0.1"])

sys.path.insert(0, str(Path(__file__).resolve().parent))
from app.server import flask_app

if __name__ == "__main__":
    print(">>> Сервер ТОиР Эксперт AI запускается на http://127.0.0.1:8000")
    print(">>> Веб-панель тестирования: http://127.0.0.1:8000/")
    print(">>> Swagger UI (/docs):      http://127.0.0.1:8000/docs")
    print(">>> Спецификация OpenAPI:     http://127.0.0.1:8000/openapi.json")
    flask_app.run(host="127.0.0.1", port=8000, threaded=True, debug=False)
