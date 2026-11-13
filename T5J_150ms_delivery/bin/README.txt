run_parachute.exe 是随包提供的原生 Windows x64 启动器。

使用方法：
1. 在交付包根目录运行 run_parachute.bat、run_resume.bat 或 run_report_only.bat。
2. 也可在命令行执行 bin\run_parachute.exe --help 查看参数。

本目录中的 runtime 包含 Python 3.8.10 x64、NumPy、SciPy、Matplotlib、
UCRT 和 VC++ 运行库。请完整保留 runtime 和上级 src 目录，不要只复制 EXE。
目标系统为 Windows 7 SP1 x64 / Windows 10 x64 / Windows 11 x64。
