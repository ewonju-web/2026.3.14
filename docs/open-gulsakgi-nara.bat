@echo off
REM Cursor를 Remote-SSH로 열 때 기본 경로: /srv/excavator/gulsakgi-nara
REM 사용 전에 SSH_HOST를 본인 SSH 접속 주소로 수정하세요. (예: root@211.110.140.201)

set SSH_HOST=root@211.110.140.201
set REMOTE_PATH=/srv/excavator/gulsakgi-nara

cursor --remote ssh-remote+%SSH_HOST% %REMOTE_PATH%
