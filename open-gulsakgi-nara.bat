@echo off
REM Cursor 실행 시 /srv/excavator/gulsakgi-nara 로 바로 열기
REM SSH_HOST 를 본인 접속 주소로 수정 (예: root@211.110.140.201)

set SSH_HOST=root@211.110.140.201
set REMOTE_PATH=/srv/excavator/gulsakgi-nara

cursor --remote ssh-remote+%SSH_HOST% %REMOTE_PATH%
