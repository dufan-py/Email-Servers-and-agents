from __future__ import annotations

from argparse import ArgumentParser #命令行参数解析
# from email.mime.text import MIMEText
from queue import Queue #先进先出 线程间通信
import socket           #网络通信
from socketserver import ThreadingTCPServer, BaseRequestHandler
from threading import Thread
import tomli
def student_id() -> int:
    return 12112811


# 定义了--name (或 -n)，--smtp (或 -s)，--pop (或 -p)作为接受的命令行参数。
parser = ArgumentParser()
parser.add_argument('--name', '-n', type=str, required=True)
parser.add_argument('--smtp', '-s', type=int)
parser.add_argument('--pop', '-p', type=int)

args = parser.parse_args()
global MAILBOXES



with open('data/config.toml', 'rb') as f:
    _config = tomli.load(f)
    SMTP_PORT = args.smtp or int(_config['server'][args.name]['smtp'])
    POP_PORT = args.pop or int(_config['server'][args.name]['pop'])
    ACCOUNTS = _config['accounts'][args.name]
    #{'usr1@mail.sustech.edu.cn': 'pass1',
    #  'usr2@mail.sustech.edu.cn': 'pass2'}
    #MAILBOXES = {account: ["123456789","123"] for account in ACCOUNTS.keys()}
    MAILBOXES = {
        'exmail.qq.com': {
            'usr1@mail.sustech.edu.cn': [],
            'usr2@mail.sustech.edu.cn': []
        },
        'gmail.com': {
            'usr@gmail.com':[]
        }
    }



with open('data/fdns.toml', 'rb') as f:
    FDNS = tomli.load(f)

ThreadingTCPServer.allow_reuse_address = True

# 根据输入的 domain和type 从FDNS字典中return相关信息
def fdns_query(domain: str, type_: str) -> str | None:
    domain = domain.rstrip('.') + '.'
    return FDNS[type_][domain]




class POP3Server(BaseRequestHandler): # 处理TCP连接
    def handle(self):
        conn = self.request # 客户端的连接对象，该对象可以用来发送和接收数据
        user = None
        password = None
        #MAILBOXES = MailBox.MAIL
        print(f"MAILBOX={MAILBOXES}")
        # 发送欢迎消息
        conn.sendall(b"+OK POP3 server ready\r\n")

        deleted_emails = []

        while True:
            data = conn.recv(1024).decode().strip()
            response = ""
            if data.startswith("USER"):
                # 错误suername
                user = data.split()[1]
                print(f"Received: b'USER {user}\r\n'")
                print("Response: +OK")
                conn.sendall(b"+OK User accepted\r\n")

            elif data.startswith("PASS"):
                password = data.split()[1]
                print(f"Received: b'PASS {password}\r\n'")
                print("Response: +OK")
                # 从config.toml获取用户的域
                user_domain = user.split('@')[-1]
                server_name = None
                for server, accounts in _config['accounts'].items():
                    if user in accounts:
                        server_name = server
                        break

                if not server_name:
                    conn.sendall(b"-ERR Unknown user\r\n")
                    return

                valid_password = _config['accounts'][server_name][user]

                if password == valid_password:
                    conn.sendall(b"+OK Password accepted\r\n")
                   # MAILBOXES[user] = MAILBOXES.get(user, [])  ########## 获取该用户的电子邮件列表
                else:
                    conn.sendall(b"-ERR Invalid password\r\n")


    ######### 处理"STAT"命令的部分，计算电子邮件数量以及总字节数，并返回给客户端：
            elif data.startswith("STAT"):
                aaa = b'STAT\r\n'
                print(f"Received: {aaa}")
                print("Response: +OK")
                num_emails = len(MAILBOXES[args.name][user])
                total_bytes =  sum(len(email.encode('utf-8')) for email in MAILBOXES[args.name][user])
                response = "+OK {} {}".format(num_emails, total_bytes)
                conn.sendall(response.encode('utf-8') + b"\r\n")


            elif data.startswith("LIST"): # [b'9', b'3']（两封邮件）
                aaa = b'LIST\r\n'
                print(f"Received: {aaa}")
                print("Response: +OK")
                response_list = []
                for index, email in enumerate(MAILBOXES[args.name][user], start=1):
                    email_size = len(email.encode('utf-8'))
                    response_list.append("{} {}".format( index,email_size))
                # Combine all responses with a newline
                combined_response = "\r\n".join(response_list)
                # Create the overall response
                response = "{}".format(combined_response)
                a = "+OK"
                conn.sendall(a.encode('utf-8') + b"\r\n")
                conn.sendall(response.encode('utf-8') + b"\r\n")
                conn.sendall(b".\r\n")

            elif data.startswith("RETR"):
                aaa = b'RETR\r\n'
                print(f"Received: {aaa}")
                print("Response: +OK")
                email_idx = int(data.split()[1]) - 1
                if email_idx >= len(MAILBOXES[args.name][user]):

                    response = "+OK\r\n not in the list\r\n"
                    conn.sendall(response.encode('utf-8') + b".\r\n")
                elif email_idx not in deleted_emails:

                    email_content = MAILBOXES[args.name][user][email_idx]
                    response = "+OK {} bytes\r\n{}\r\n".format(len(email_content.encode('utf-8')), email_content)
                    conn.sendall(response.encode('utf-8') )
                else:
                    conn.sendall(b"-ERR message marked for deletion\r\n")

            elif data.startswith("DELE"):
                email_idx = int(data.split()[1]) - 1
                if email_idx not in deleted_emails:
                    deleted_emails.append(email_idx)
                    response = "+OK message {} deleted\r\n".format(email_idx + 1)
                    conn.sendall(response.encode('utf-8'))
                else:
                    response = "-ERR message {} already deleted\r\n".format(email_idx + 1)
                    conn.sendall(response.encode('utf-8'))

            elif data.startswith("RSET"):
                deleted_emails.clear()
                conn.sendall(b"+OK deletions cleared\r\n")

            elif data.startswith("NOOP"):
                conn.sendall(b"+OK\r\n")

            elif data.startswith("QUIT"):
                # 删除标记为删除的邮件
                for idx in sorted(deleted_emails, reverse=True):
                    del MAILBOXES[args.name][user][idx]

                deleted_emails.clear()
                #MailBox.MAIL=MAILBOXES
                # 发送响应给客户端
                conn.sendall(b"+OK\r\n")
                # 关闭连接，结束会话
                conn.close()

            else:
                conn.sendall(b"-ERR Unknown command\r\n")



class SMTPServer(BaseRequestHandler):   #继承BaseRequestHandler类
    def handle(self):
        conn = self.request  # 获取到客户端的连接对象
        sender = None  # 发件人地址初始化为空
        data_mode = False  # 数据模式标识，用于标识是否处于收取邮件内容状态
        #MAILBOXES = MailBox.MAIL
        # 发送欢迎消息
        conn.sendall(b"220 SMTP Server2 ready\r\n")
        receiver = []

        while True:
            try:
                data = conn.recv(1024).decode().strip()  # 从客户端接收数据，并去除两边的空白字符
                if not data:
                    break  # 如果没有接收到数据，退出循环
                # 如果处于数据模式，收集邮件数据
                if data_mode:
                    if data == ".":
                        data_mode = False  # 当收到单独一个句点时，表示邮件内容结束
                        # 在这里处理email_data（例如保存到邮箱或转发到Server2）
                        conn.sendall(b"250 OK: Message received\r\n")
                    else:

                        for i in receiver:
                            receiver_ = i.strip("<>")
                            print("receiver_:")
                            print(receiver_)
                            if receiver_.endswith("edu.cn") and args.name == "exmail.qq.com":
                                MAILBOXES["exmail.qq.com"][receiver_].append(data)
                            elif receiver_.endswith("gmail.com") and args.name == "gmail.com":
                                MAILBOXES["gmail.com"][receiver_].append(data)
                            elif receiver_ != "usr1@mail.sustech.edu.cn" and receiver_ != "usr2@mail.sustech.edu.cn" and receiver_ != "usr@gmail.com":
                                MAILBOXES[args.name][receiver_].append(data)
                                conn.sendall(b"550 No such user here\r\n")
                            else:
                                self.Sendmail(sender, receiver_, data)

                        if data.endswith("."):
                            data_mode=False
                            conn.sendall(b"250 OK: Message received\r\n")
                    continue
                # 处理SMTP命令
                if data.startswith("helo") or data.startswith("ehlo"):
                    #domain = data.split()[1]  # 获取到客户端提供的域名
                    conn.sendall(b"250 OK\r\n")

                elif data.startswith("mail FROM:"):
                    sender = data[10:]  # 获取发件人地址
                    conn.sendall(b"250 OK: Sender address accepted\r\n")

                elif data.startswith("rcpt TO:"):

                    print("data:")
                    print(data)
                    print(data[8:])
                    receiver.append(data[8:])






                    conn.sendall(b"250 OK: Recipient address accepted\r\n")

                elif data.startswith("data"):
                    data_mode = True  # 当收到DATA命令时，进入数据模式
                    conn.sendall(b"354 Start mail input; end with <CRLF>.<CRLF>\r\n")

                elif data.startswith("quit"):
                    conn.sendall(b"221 Closing connection. Goodbye!\r\n")  # 当收到QUIT命令时，发送退出信息，并在循环外关闭连接
                    #MailBox.MAIL=MAILBOXES
                    break

                else:
                    conn.sendall(b"502 Command not implemented\r\n")  # 对于不支持的SMTP命令，发送错误消息


            except socket.timeout:  # 捕获超时异常

                conn.sendall(b"421 Timeout. Trying to continue...\r\n")

                continue  # 使用continue来继续执行下一次循环

            except socket.error as e:  # 捕获其他socket错误

                conn.sendall(f"421 Connection error: {str(e)}. Trying to continue...\r\n".encode())

                continue  # 使用continue来继续执行下一次循环

            except Exception as e:  # 捕获所有其他异常

                conn.sendall(f"421 Unexpected error: {str(e)}. Trying to continue...\r\n".encode())

                continue



    def Sendmail(self,sender,receiver,msg):
        print("Sendmail")
        if receiver.endswith("edu.cn"):
            TO_SERVER = fdns_query("mail.sustech.edu.cn.",'MX')
        elif receiver.endswith("gmail.com"):
            TO_SERVER = fdns_query("gmail.com.", 'MX')
            # 目标端口 int(fdns_query(SMTP_SERVER, 'P'))

        client_socket = socket.socket(socket.AF_INET, socket.SOCK_STREAM)
        client_socket.connect(('192.168.43.205', int(fdns_query(TO_SERVER, 'P'))))
	
        client_socket.recv(1024)

        client_socket.send(b'ehlo localhost\r\n')
        client_socket.recv(1024)

        client_socket.send(b'mail FROM:' + sender.encode('utf-8') + b'\r\n')
        client_socket.recv(1024)

        client_socket.send(b'rcpt TO:<' + receiver.encode('utf-8') + b'>' + b'\r\n')
        client_socket.recv(1024)

        client_socket.send(b'data\r\n')
        client_socket.recv(1024)

        client_socket.send(msg.encode('utf-8'))
        client_socket.send(b'\r\n.\r\n')
        client_socket.recv(1024)

        client_socket.send(b'quit\r\n')
        client_socket.recv(1024)

        client_socket.close()

        print('[Server] Sent message to another server done')


if __name__ == '__main__':
    if student_id() % 10000 == 0:
        raise ValueError('Invalid student ID')

    smtp_server = ThreadingTCPServer(('', SMTP_PORT), SMTPServer)
    pop_server = ThreadingTCPServer(('', POP_PORT), POP3Server) #设置POP监听的端口
    Thread(target=smtp_server.serve_forever).start()
    Thread(target=pop_server.serve_forever).start()
