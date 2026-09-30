# CyberRecon — Use Case Diagram

**Format:** PlantUML

**Source file:** [use-case.puml](use-case.puml)

## Rendered Diagram

![Use Case Diagram](use-case.png)

## PlantUML Source

```plantuml
@startuml
left to right direction
skinparam packageStyle rectangle
skinparam actorStyle awesome
title CyberRecon - QR-C2 Framework - Use Case Diagram

actor "Operator" as OP
actor "Victim Host" as VH
actor "Defender" as DF
actor "C2 Server" as C2

rectangle "CyberRecon - QR-Code-Based C2 Framework" {
    usecase "Authenticate Operator" as UC1
    usecase "Register Victim" as UC2
    usecase "Send Command" as UC3
    usecase "Queue Command" as UC4
    usecase "Fetch QR Command" as UC5
    usecase "Decode QR Payload" as UC6
    usecase "Execute RAT Command" as UC7
    usecase "Exfiltrate Data" as UC8
    usecase "Store Exfil Data" as UC9
    usecase "View Dashboard" as UC10
    usecase "Download Exfil ZIP" as UC11
    usecase "Parse NL Command" as UC12
    usecase "Locate via GPS" as UC13
    usecase "Capture Screenshot" as UC14
    usecase "Monitor Keystrokes" as UC15
}

OP --> UC1
OP --> UC3
OP --> UC10
OP --> UC11
OP --> UC12
VH --> UC2
VH --> UC5
VH --> UC7
VH --> UC8
C2 --> UC4
C2 --> UC9
DF --> UC12 : reads IOCs

UC3 ..> UC1 : <<include>>
UC3 ..> UC4 : <<include>>
UC5 ..> UC6 : <<include>>
UC6 ..> UC7 : <<include>>
UC7 ..> UC8 : <<include>>
UC7 ..> UC13 : <<include>>
UC7 ..> UC14 : <<include>>
UC7 ..> UC15 : <<include>>
UC8 ..> UC9 : <<include>>
UC11 ..> UC1 : <<include>>

@enduml
```