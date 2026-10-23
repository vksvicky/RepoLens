def read_config():
    try:
        return open("config.txt").read()
    except OSError:
        return ""
