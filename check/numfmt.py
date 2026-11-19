def fmt_num(v):
    """数値の表示用整形：小数は最大3桁・末尾の0を消す、整数値は「.0」を付けない。"""
    if isinstance(v, float):
        if v.is_integer():
            return str(int(v))
        return f"{v:.3f}".rstrip('0').rstrip('.')
    return str(v)
