def bold_text(value):
    result = []
    for char in str(value):
        code = ord(char)
        if 65 <= code <= 90:
            result.append(chr(0x1D5D4 + code - 65))
        elif 97 <= code <= 122:
            result.append(chr(0x1D5EE + code - 97))
        elif 48 <= code <= 57:
            result.append(chr(0x1D7EC + code - 48))
        else:
            result.append(char)
    return "".join(result)
