def classify(x):
    if x < 0:
        return "n"
    elif x == 0:
        return "z"
    else:
        if x > 100:
            return "b"
        return "p"
