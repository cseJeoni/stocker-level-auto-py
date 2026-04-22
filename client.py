import socket
import time

# Equipment simulator for end-to-end testing of the measurement flow.
# Replicates the command protocol that the real stocker controller uses.

server_address = "127.0.0.1"
server_port = 5000

shelf_list = ["1-1-1", "1-1-2", "1-1-3", "1-1-4", "1-1-5", "1-1-6", "1-1-7", "1-1-8", "1-1-9", "1-1-10",
              "2-1-1", "2-1-2", "2-1-3", "2-1-4", "2-1-5", "2-1-6", "2-1-7", "2-1-8", "2-1-9", "2-1-10"]

client_socket = socket.socket(socket.AF_INET, socket.SOCK_STREAM)
# 12-second timeout acts as the equipment-side safety timer. It is intentionally
# longer than the server's BLE_READ_TIMEOUT (10s) to allow the Python server to
# detect and report a BLE error before the equipment declares a timeout itself.
client_socket.settimeout(12.0)
client_socket.connect((server_address, server_port))

try:
    for shelf in shelf_list:
        print(f"\n[설비] {shelf} 위치로 이동 중...")
        time.sleep(2)  # Simulates travel and mechanical stabilization time.

        client_socket.sendall(f"MEASURE|{shelf}\n".encode("utf-8"))
        print(f"[설비] {shelf} 안착 및 측정 요청 송신.")

        try:
            data = client_socket.recv(1024).decode("utf-8")
            if f"DONE|{shelf}" in data:
                print(f"[설비] 서버 응답 수신: {shelf} 입력 완료 확인.")
                print("--------------------------------------")
            elif "ERROR" in data:
                # Server detected a BLE failure; abort the run.
                print(f"[설비] 에러 응답 수신: {data.strip()}. 중단합니다.")
                break
            else:
                print(f"[설비] 예상치 못한 응답 수신: {data.strip()}. 중단합니다.")
                break

        except socket.timeout:
            # No response within 12 seconds. Notify the server before disconnecting
            # so it can log the correct failure reason.
            print(f"[설비] ⏱️ 서버 응답 타임아웃! (12초 초과)")
            client_socket.sendall(f"TIMEOUT|{shelf}\n".encode("utf-8"))
            break

    # Sent after normal completion or after an error break to signal session end.
    client_socket.sendall("FINISH\n".encode("utf-8"))
    print("\n[설비] 측정 루틴 종료 (FINISH 송신 완료).")

except Exception as e:
    print(f"[설비] 통신 에러 발생: {e}")
finally:
    client_socket.close()
