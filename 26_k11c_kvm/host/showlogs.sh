for f in b1 b2 b3 b4 b5 b6; do echo == $f; grep -E 'last-message|ERROR|WARN' /tmp/$f.log | tail -2 | cut -c1-240; done
