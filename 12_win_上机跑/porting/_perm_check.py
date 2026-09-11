import os
paths = [
    r'D:/win_game_project/.workbuddy/memory/2026-09-10.md',
    r'D:/win_game_project/03_ai的记忆_和skill/04_workbuddy_记忆与skill/日志/2026-09-10.md',
]
for p in paths:
    print('==', p)
    try:
        st = os.stat(p)
        print('   exists, mode=', oct(st.st_mode), 'size=', st.st_size)
        print('   readonly bit:', not (st.st_mode & 0o200))
        print('   access W_OK:', os.access(p, os.W_OK))
    except Exception as e:
        print('   stat FAIL:', type(e).__name__, e)
    try:
        f = open(p, 'a', encoding='utf-8')
        f.close()
        print('   open(append): OK  <-- 可写')
    except Exception as e:
        print('   open(append): FAIL:', type(e).__name__, e)
