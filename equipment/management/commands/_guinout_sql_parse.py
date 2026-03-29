# -*- coding: utf-8 -*-
"""tb_guinout mysqldump INSERT 한 줄 파서 (import_direct_nara_jobs 전용)."""


def _parse_mysql_value(line: str, i: int):
    n = len(line)
    while i < n and line[i] in " \t":
        i += 1
    if i >= n:
        return None, i
    if line[i] == "'":
        i += 1
        parts = []
        while i < n:
            c = line[i]
            if c == "\\":
                i += 1
                if i >= n:
                    break
                esc = line[i]
                if esc == "n":
                    parts.append("\n")
                elif esc == "r":
                    parts.append("\r")
                elif esc == "t":
                    parts.append("\t")
                elif esc == "0":
                    parts.append("\0")
                elif esc == "Z":
                    parts.append("\x1a")
                else:
                    parts.append(esc)
                i += 1
                continue
            if c == "'":
                if i + 1 < n and line[i + 1] == "'":
                    parts.append("'")
                    i += 2
                    continue
                i += 1
                return ("".join(parts), i)
            parts.append(c)
            i += 1
        return ("".join(parts), i)
    j = i
    if j < n and line[j] == "-":
        j += 1
    while j < n and line[j].isdigit():
        j += 1
    num_s = line[i:j]
    if not num_s:
        return None, i
    try:
        return int(num_s), j
    except ValueError:
        return num_s, j


def iter_tb_guinout_rows_from_dump(path: str):
    """yield 32칼럼 리스트 (uid, title, mode, viewtype, lcode, ... reg_date)."""
    mark = "INSERT INTO `tb_guinout` VALUES "
    cols = 32
    with open(path, "r", encoding="utf-8", errors="replace") as f:
        for line in f:
            if mark not in line:
                continue
            pos = line.find(mark) + len(mark)
            n = len(line)
            while pos < n:
                while pos < n and line[pos] in " \t\r\n":
                    pos += 1
                if pos >= n or line[pos] != "(":
                    break
                pos += 1
                vals = []
                for col in range(cols):
                    if col > 0:
                        while pos < n and line[pos] in " \t":
                            pos += 1
                        if pos < n and line[pos] == ",":
                            pos += 1
                    v, pos = _parse_mysql_value(line, pos)
                    vals.append(v)
                while pos < n and line[pos] in " \t":
                    pos += 1
                if pos < n and line[pos] == ")":
                    pos += 1
                yield vals
                while pos < n and line[pos] in " \t\r\n":
                    pos += 1
                if pos < n and line[pos] == ",":
                    pos += 1
                elif pos < n and line[pos] == ";":
                    break
