# Cursor 실행 시 기본으로 이 폴더 열기

Remote-SSH로 접속한 뒤 Cursor를 켜면 **항상 `/srv/excavator/gulsakgi-nara`만** 열리게 하는 방법입니다.

---

## 방법 1: 실행 스크립트 사용 (권장)

집/회사 PC에 아래 스크립트를 두고, **Cursor 대신 이 스크립트를 실행**하면 해당 경로로 바로 열립니다.

### Windows

1. `docs/open-gulsakgi-nara.bat` 내용을 참고해 PC에 `open-gulsakgi-nara.bat` 저장 (바탕화면 등).
2. `SSH_HOST` 부분을 본인 SSH 접속 주소로 수정 (예: `root@211.110.140.201` 또는 SSH 설정에 쓴 호스트 이름).
3. 바탕화면 등에서 **bat 파일 더블클릭** → Cursor가 해당 경로로 열림.

### macOS / Linux

1. `docs/open-gulsakgi-nara.sh` 를 PC에 복사 후 실행 권한 부여:  
   `chmod +x open-gulsakgi-nara.sh`
2. `SSH_HOST` 를 본인 SSH 접속 주소로 수정.
3. 터미널에서 `./open-gulsakgi-nara.sh` 실행 또는 더블클릭 → Cursor가 해당 경로로 열림.

---

## 방법 2: Cursor가 마지막 창 복원하도록 설정

한 번 **gulsakgi-nara 워크스페이스**로 열어 둔 뒤, Cursor를 종료했다가 다시 켜면 **같은 창이 다시 열리게** 할 수 있습니다.

1. **Cursor** 실행 → Remote-SSH로 접속 → **파일 → 워크스페이스에서 열기** →  
   `/srv/excavator/gulsakgi-nara/gulsakgi-nara.code-workspace` 선택해서 한 번 열기.
2. Cursor **설정** (Ctrl+,) → 검색창에 `restore` 입력.
3. **Window: Restore Windows** 를 **all** 로 설정 (마지막에 열었던 창들 복원).
4. 이후 Cursor를 종료했다가 다시 실행하면, 마지막에 열었던 gulsakgi-nara 창이 다시 열립니다.

---

## 요약

- **매번 이 경로만 열고 싶다** → 방법 1 스크립트를 Cursor 대신 실행.
- **한 번 열어 둔 걸 다시 쓰고 싶다** → 방법 2로 복원 설정 후, gulsakgi-nara 워크스페이스를 마지막으로 열어 두고 사용.
