\# Data Flow Diagram



```mermaid

flowchart LR

&#x20;   OP\[Operator] -->|command| C2\[C2 Server]

&#x20;   C2 -->|JSON| B64\[base64 encoder]

&#x20;   B64 -->|payload| QR\[QR generator]

&#x20;   QR -->|PNG| VICTIM\[Victim Browser]

&#x20;   VICTIM -->|screenshot| CV\[OpenCV decoder]

&#x20;   CV -->|JSON| DISP\[Command dispatcher]



&#x20;   DISP -->|screenshot| SS\[Screenshot module]

&#x20;   DISP -->|keystrokes| KL\[Keylogger module]

&#x20;   DISP -->|gps| GPS\[GPS module]

&#x20;   DISP -->|processes| PR\[Process module]



&#x20;   SS -->|base64| EXFIL\[POST /exfil]

&#x20;   KL -->|base64| EXFIL

&#x20;   GPS -->|JSON| EXFIL

&#x20;   PR -->|JSON| EXFIL



&#x20;   EXFIL -->|stores| STORE\[(C2 Store)]

&#x20;   STORE -->|renders| DASH\[Dashboard]

&#x20;   STORE -->|ZIP| DL\[/download-all]

```

