import sys
import socket
import asyncio
import threading
import traceback
import datetime
from PyQt5.QtCore import QObject, pyqtSignal
import config
from ble_module import BleHandler
from csv_module import CSVHandler

class AutomationServer(QObject):
    # 백그라운드 스레드에서 UI 화면(표, 로그)을 직접 건드리면 안 되므로,
    # 데이터를 안전하게 전달하기 위해 Signal (신호) 객체 생성 
    log_signal = pyqtSignal(str) # 로그 텍스트를 UI에 전달 
    table_signal = pyqtSignal(list) # CSV에 기록된 데이터 한 줄을 UI 표에 전달 

    def __init__(self, ble_address, stocker_id):
        super().__init__()
        # 블루투스와 CSV 핸들러 초기화 
        self.ble = BleHandler(ble_address)
        self.csv = CSVHandler(stocker_id)
        self.is_running = True

        # daemon=True: 메인 프로그램 창의 X 버튼을 눌러서 끄면, 이 백그라운드 스레드도 즉시 종료됨 
        self._thread = threading.Thread(target=self._run, daemon=True)

    def start(self):
        # UI에서 READY 버튼을 누르면 백그라운드 스레드 시작 
        self._thread.start()

    def _run(self):
        # 스레드의 최상위 실행 함수
        # 백그라운드 스레드에서 에러가 나면 콘솔에 안 찍히고 프로그램이 죽어버리는 것을 방지 
        try:
            self._run_internal()
        except Exception:
            # 치명적 오류 발생 시 에러 내용을 파일(crash_log.txt)로 남기고 UI에 알림 
            _write_crash_log(traceback.format_exc())
            self.log_signal.emit("❌ [시스템] 치명적 오류 발생 (crash_log.txt 확인)")

    def _run_internal(self):
        # 실제 서버 통신과 블루투스 제어가 이루어지는 메인 로직 
        loop = asyncio.new_event_loop()
        asyncio.set_event_loop(loop)

        # 1. 블루투스 기기 연결 시도 
        try:
            loop.run_until_complete(self.ble.connect())
        except Exception as e:
            self.log_signal.emit(f"❌ [시스템] 레벨기 연결 실패: {e}")
            loop.close()
            return
        
        # 2. TCP/IP 소켓 서버 설정
        server = socket.socket(socket.AF_INET, socket.SOCK_STREAM)
        # 이미 사용 중인 포트 오류 (TIME_WAIT) 방지를 위한 옵션 
        server.setsockopt(socket.SOL_SOCKET, socket.SO_REUSEADDR, 1)
        try:
            server.bind((config.SERVER_HOST, config.SERVER_PORT))
        except OSError as e:
            self.log_signal.emit(f"❌ [시스템] 포트 {config.SERVER_PORT} 바인딩 실패: {e}")
            loop.run_until_complete(self.ble.disconnect())
            loop.close()
            return

        server.listen(1)
        server.settimeout(1.0) # 1초마다 타임아웃을 발생시켜 while 루프의 is_running 상태를 체크할 수 있게 함 

        self.log_signal.emit(f"🚀 서버 가동 중 (저장경로: 다운로드 폴더)")

        # 3. 클라이언트(설비) 접속 대기 루프 
        while self.is_running:
            try:
                client, addr = server.accept()
                while self.is_running:
                    # 설비로부터 전송된 메시지 수신 (버퍼 1024 bytes)
                    data = client.recv(1024).decode('utf-8')
                    if not data:
                        break # 연결이 끊기면 안쪽 루프 탈출

                    msg = data.strip()
                    self.log_signal.emit(f"📥 수신 : {msg}")

                    # [케이스 1] 측정 요청 수신 시 
                    if msg.startswith("MEASURE|"):
                        loc = msg.split("|")[1] # 쉘프 위치 값 추출 
                        try:
                            # 설정된 시간 (기본 10초) 동안 레벨기에서 값을 읽어옴 (내부적으로 5회 평균 처리)
                            x, y = loop.run_until_complete(
                                asyncio.wait_for(self.ble.read_level_data(), timeout=config.BLE_READ_TIMEOUT)
                            )
                            if x is not None:
                                # CSV 파일에 기록 
                                res = self.csv.write_row(loc, x, y)
                                if res:
                                    # UI 표 업데이트 및 정상 완료 응답 송신 
                                    self.table_signal.emit(res)
                                    self.log_signal.emit(f"✅ 기록 완료 : {loc} (X:{x}, Y:{y})")
                                    client.sendall(f"DONE|{loc}\n".encode('utf-8'))
                            else:
                                raise Exception("READ_ERROR")
                        except Exception:
                            # 10초 내에 블루투스에서 값을 못 가져오면 파이썬 측 타임아웃 에러 송신 
                            self.log_signal.emit(f"❌ 에러 : 블루투스 연결 확인 필요 ({loc})")
                            client.sendall(f"ERROR|BLE_DISCONNECT|{loc}\n".encode('utf-8'))

                    # [케이스 2] 설비 측에서 12초 이상 대기하다가 스스로 타임아웃을 선언했을 때 
                    elif msg.startswith("TIMEOUT|"):
                        loc = msg.split("|")[1]
                        # 실제 원인이 블루투스 끊김인지 파이썬 렉인지 구분하여 로그 출력 
                        status = "연결 끊김" if not (self.ble.client and self.ble.client.is_connected) else "응답 지연"
                        self.log_signal.emit(f"⚠️ 타임아웃 : 설비 중단 알림 ({loc}) - 사유: {status}")
                        break

                    # [케이스 3] 전체 루틴 종료 시 
                    elif msg == "FINISH":
                        self.log_signal.emit(f"💾 완료 : CSV 저장 및 세션 종료")
                        break

                client.close()
            except socket.timeout:
                # 1초 타임아웃 발생 발생 시 다시 루프 처음으로 돌아가 is_running을 체크함 
                continue

        # 서버 종료 시 블루투스 연결 해제 및 리소스 정리 
        loop.run_until_complete(self.ble.disconnect())
        server.close()
        loop.close()


def _write_crash_log(text):
    # 스레드에서 잡히지 않은 에러를 텍스트 파일로 저장하는 유틸리티
    # exe 파일 빌드 후 터미널 창이 없을 때 원인 분석에 쓰임 
    try:
        log_path = "crash_log.txt"
        with open(log_path, "a", encoding="utf-8") as f:
            f.write(f"\n=== CRASH {datetime.datetime.now()} ===\n")
            f.write(text)
            f.write("\n")
    except Exception:
        pass
