import subprocess
import re

print("Starting SSH Pinggy Tunnel with -T...", flush=True)
# Start ssh process
process = subprocess.Popen(
    ['ssh', '-T', '-o', 'StrictHostKeyChecking=no', '-p', '443', '-R', '80:127.0.0.1:5000', 'pinggy@a.pinggy.io'],
    stdin=subprocess.DEVNULL,
    stdout=subprocess.PIPE,
    stderr=subprocess.STDOUT,
    text=True,
    bufsize=1
)

# Open log file
with open('tunnel.log', 'w', encoding='utf-8') as log_file:
    # Read output line by line and write to file
    for line in iter(process.stdout.readline, ''):
        log_file.write(line)
        log_file.flush()
        print(line, end='', flush=True)
        
        # Capture the public HTTPS URL
        match = re.search(r'https://[a-zA-Z0-9.-]+\.(?:pinggy-free\.link|pinggy\.net)', line)
        if match:
            url = match.group(0)
            print(f"\n[Tunnel Script] Captured public URL: {url}", flush=True)
            with open('public_url.txt', 'w', encoding='utf-8') as f:
                f.write(url)
                
        # Terminate if the process dies
        if process.poll() is not None:
            break
