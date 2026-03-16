import socket
import struct
import time
import select
import sys

def get_hostname(ip):
    """Получение имени хоста по IP через обратный DNS"""
    try:
        return socket.gethostbyaddr(ip)[0]
    except socket.herror:
        return ip

def traceroute(dest_name, max_hops=30, packets_per_hop=3, resolve_hostnames=False, timeout=10.0):
    try:
        dest_addr = socket.gethostbyname(dest_name)
    except socket.gaierror as e:
        print(f"Не удалось разрешить имя хоста {dest_name}: {e}")
        return

    print(f"Трассировка маршрута к {dest_name} [{dest_addr}] с максимум {max_hops} прыжков:")

    local_ip = "0.0.0.0"

    try:
        icmp_sock = socket.socket(socket.AF_INET, socket.SOCK_RAW, socket.IPPROTO_ICMP)
        icmp_sock.settimeout(timeout)
        icmp_sock.bind((local_ip, 0))
    except OSError as e:
        print(f"Ошибка создания ICMP сокета: {e}")
        return

    try:
        base_port = 33434
        port_increment = 0

        for ttl in range(1, max_hops + 1):
            try:
                udp_sock = socket.socket(socket.AF_INET, socket.SOCK_DGRAM, socket.IPPROTO_UDP)
                udp_sock.setsockopt(socket.IPPROTO_IP, socket.IP_TTL, ttl)
                udp_sock.settimeout(timeout)
            except OSError:
                udp_sock.close()
                continue

            times = []
            current_addr = None

            for i in range(packets_per_hop):
                current_port = base_port + port_increment
                port_increment += 1

                start_time = time.time()
                try:
                    udp_sock.sendto(b"test", (dest_addr, current_port))
                    ready = select.select([icmp_sock], [], [], timeout)
                    if ready[0]:
                        data, addr = icmp_sock.recvfrom(8192)
                        ihl = (data[0] & 0x0F) * 4
                        if len(data) >= ihl + 8:
                            icmp_type, code = struct.unpack('!BB', data[ihl:ihl+2])
                            if icmp_type in (3, 11):
                                end_time = time.time()
                                times.append((end_time - start_time) * 1000)
                                current_addr = addr[0]
                    else:
                        times.append('*')
                except (socket.timeout, OSError):
                    times.append('*')

            udp_sock.close()

            times_str = ' '.join(f"{t:.2f} ms" if isinstance(t, float) else t for t in times)
            if current_addr:
                # Всегда пытаемся получить доменное имя
                hostname = get_hostname(current_addr)
                # Если доменное имя отличается от IP, показываем оба (как в traceroute)
                if hostname != current_addr:
                    node_info = f"{hostname} ({current_addr})"
                else:
                    node_info = current_addr
                print(f"{ttl:2d}    {times_str}    {node_info}")
            else:
                print(f"{ttl:2d}    {times_str}")

            if current_addr == dest_addr:
                break

    except KeyboardInterrupt:
        print("\nПрервано пользователем. Завершение трассировки.")
    finally:
        icmp_sock.close()

if __name__ == "__main__":
    if len(sys.argv) < 2:
        print("Использование: python traceroute.py <host> [-r] [-h <max_hops>]")
        sys.exit(1)
    dest = sys.argv[1]
    resolve_hostnames = '-r' in sys.argv  # Этот флаг теперь не нужен, но оставим для совместимости
    max_hops = 15
    if '-h' in sys.argv:
        try:
            hop_index = sys.argv.index('-h') + 1
            max_hops = int(sys.argv[hop_index])
        except (ValueError, IndexError):
            print("Укажи корректное число прыжков после -h")
            sys.exit(1)
    traceroute(dest, max_hops=max_hops, resolve_hostnames=resolve_hostnames)
