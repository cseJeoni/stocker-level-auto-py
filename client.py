import socket
import time

server_address = "127.0.0.1"
server_port = 5000

# 쉘프 예시
shelf_list = ["1-1-1", "1-1-2", "1-1-3", "1-1-4", "1-1-5", "1-1-6", "1-1-7", "1-1-8", "1-1-9", "1-1-10",
              "2-1-1", "2-1-2", "2-1-3", "2-1-4", "2-1-5", "2-1-6", "2-1-7", "2-1-8", "2-1-9", "2-1-10"]

client_socket = socket.socket(socket.AF_INET, socket.SOCK_STREAM)
client_socket.settimeout(12.0) 
client_socket.connect((server_address, server_port))

try:
    for shelf in shelf_list:
        print(f"\n[설비] {shelf} 위치로 이동 중...")
        time.sleep(2) 
        
        msg = f"MEASURE|{shelf}\n"
        client_socket.sendall(msg.encode("utf-8"))
        print(f"[설비] {shelf} 안착 및 측정 요청 송신.")

        try:
            data = client_socket.recv(1024).decode("utf-8")
            if f"DONE|{shelf}" in data:
                print(f"[설비] 서버 응답 수신: {shelf} 입력 완료 확인.")
                print("--------------------------------------")
            # 파이썬에서 에러를 보냈을 때의 처리
            elif "ERROR" in data:
                print(f"[설비] 에러 응답 수신: {data.strip()}. 중단합니다.")
                break
            else:
                print(f"[설비] 예상치 못한 응답 수신: {data.strip()}. 중단합니다.")
                break
                
        # 12초 동안 아무 응답이 없으면 타임아웃 처리
        except socket.timeout:
            print(f"[설비] ⏱️ 서버 응답 타임아웃! (12초 초과)")
            # 파이썬 쪽에 타임아웃 났다고 알려줌
            client_socket.sendall(f"TIMEOUT|{shelf}\n".encode("utf-8"))
            break

    # 루프가 완전히 끝난 후 최종적으로 FINISH 송신 (타임아웃으로 break 되어도 에러가 아니면 보냄)
    client_socket.sendall("FINISH\n".encode("utf-8"))
    print("\n[설비] 측정 루틴 종료 (FINISH 송신 완료).")

except Exception as e:
    print(f"[설비] 통신 에러 발생: {e}")
finally:
    client_socket.close()