import socket
import time

server_address = "127.0.0.1"
server_port = 5000

# 테스트할 위치 목록
shelf_list = ["1-1-1", "1-1-2", "1-1-3", "1-1-4", "1-1-5", "1-1-6", "1-1-7", "1-1-8",
              "2-1-1", "2-1-2", "2-1-3", "2-1-4", "2-1-5", "2-1-6", "2-1-7", "2-1-8"]

client_socket = socket.socket(socket.AF_INET, socket.SOCK_STREAM)
client_socket.connect((server_address, server_port))

try:
    for shelf in shelf_list:
        # 1. 이동 및 안착 시뮬레이션
        print(f"\n[설비] {shelf} 위치로 이동 중...")
        time.sleep(2) # 이동 시간 대기
        
        # 2. 측정 명령 전송
        msg = f"MEASURE|{shelf}\n"
        client_socket.sendall(msg.encode("utf-8"))
        print(f"[설비] {shelf} 안착 및 측정 요청 송신.")

        # 3. 서버로부터 DONE 응답 올 때까지 대기 (Blocking)
        data = client_socket.recv(1024).decode("utf-8")
        if f"DONE|{shelf}" in data:
            print(f"[설비] 서버 응답 수신: {shelf} 입력 완료 확인.")
            print("--------------------------------------")
        else:
            print("[설비] 예상치 못한 응답 수신. 중단합니다.")
            break

    # 4. 전체 종료 신호 송신
    client_socket.sendall("FINISH\n".encode("utf-8"))
    print("\n[설비] 모든 측정 완료 후 종료.")

finally:
    client_socket.close()