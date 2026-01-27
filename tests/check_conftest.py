# check_conftest.py (в папке tests)
import sys
import os

# Копируем логику из conftest.py
current_dir = os.path.dirname(os.path.abspath(__file__))
project_root = os.path.dirname(current_dir)
src_path = os.path.join(project_root, "src")

print(f"1. Текущая папка: {current_dir}")
print(f"2. Корень проекта: {project_root}")
print(f"3. Путь к src: {src_path}")
print(f"4. Существует src: {os.path.exists(src_path)}")

sys.path.insert(0, src_path)
print(f"5. Добавили в sys.path: {src_path}")

print("\n6. Пробуем импортировать...")
try:
    import logwatcher
    print(f"   ✅ logwatcher: {logwatcher}")
    print(f"   Файл пакета: {logwatcher.__file__}")
    
    from logwatcher.watcher import LogWatcher
    print(f"   ✅ LogWatcher: {LogWatcher}")
    
    print("\n🎉 Всё работает! conftest.py должен работать.")
    
except ImportError as e:
    print(f"   ❌ Ошибка: {e}")
    
    print("\nСодержимое src папки:")
    if os.path.exists(src_path):
        for item in os.listdir(src_path):
            item_path = os.path.join(src_path, item)
            if os.path.isdir(item_path):
                print(f"  📁 {item}/")
                for subitem in os.listdir(item_path):
                    print(f"     - {subitem}")
            else:
                print(f"  📄 {item}")