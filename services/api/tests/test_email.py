import asyncio
from app.integrations.email import send_approved_email
from app.core.config import settings


async def test_real_smtp_transport_to_controlled_test_sink(monkeypatch):
    """Exercises real smtplib TCP I/O, not a claim of Mailpit or external delivery."""
    captured=[]
    async def sink(reader,writer):
        writer.write(b'220 test-sink ESMTP\r\n');await writer.drain()
        while line:=await reader.readline():
            command=line.upper()
            if command.startswith(b'EHLO'):
                writer.write(b'250-test-sink\r\n250 SIZE 1048576\r\n')
            elif command.startswith((b'MAIL',b'RCPT',b'RSET',b'NOOP')):
                writer.write(b'250 OK\r\n')
            elif command.startswith(b'DATA'):
                writer.write(b'354 Send content\r\n');await writer.drain();data=[]
                while (line:=await reader.readline())!=b'.\r\n':data.append(line)
                captured.append(b''.join(data));writer.write(b'250 captured for test\r\n')
            elif command.startswith(b'QUIT'):
                writer.write(b'221 Bye\r\n');await writer.drain();break
            await writer.drain()
        writer.close();await writer.wait_closed()
    server=await asyncio.start_server(sink,'127.0.0.1',0)
    config=settings()
    monkeypatch.setattr(config,'smtp_host','127.0.0.1');monkeypatch.setattr(config,'smtp_port',server.sockets[0].getsockname()[1])
    monkeypatch.setattr(config,'smtp_sandbox',True)
    try:
        result=await send_approved_email({'recipient':'synthetic@example.test','subject':'Approved test','body':'Exact reviewed content'},'<fixed-test@switchops.test>')
        assert result=='sandbox_accepted'
        assert b'Exact reviewed content' in captured[0] and b'synthetic@example.test' in captured[0]
    finally:
        server.close();await server.wait_closed()
