package com.crinity.lhams;

import java.io.IOException;
import java.nio.file.*;
import java.nio.file.attribute.PosixFileAttributeView;
import java.nio.file.attribute.UserPrincipal;
import java.time.LocalDateTime;
import java.time.format.DateTimeFormatter;
import java.util.HashMap;
import java.util.Map;
import java.util.concurrent.ConcurrentHashMap;

import static java.nio.file.StandardWatchEventKinds.*;

/**
 * LHAMS FileAuditWatcher
 * ----------------------
 * 크리니티 웹메일(Java/Tomcat) 서버에 임베딩 가능한 파일 감사 워처.
 * Python 에이전트를 사용할 수 없는 환경(순수 Java 스택)을 위한 대안 구현.
 *
 * - java.nio WatchService 로 디렉토리(재귀) 감시
 * - 생성/수정/삭제 이벤트를 lhams_audit_java.log 에 파이프 구분 포맷으로 기록
 * - 파일 소유자(owner) 조회 (POSIX)
 *
 * 컴파일/실행:
 *   javac -d out java/src/com/crinity/lhams/FileAuditWatcher.java
 *   java -cp out com.crinity.lhams.FileAuditWatcher /mail/test_monitor
 *
 * 웹메일 임베딩 시: ServletContextListener 의 contextInitialized 에서
 * new Thread(new FileAuditWatcher(watchDir, logDir)).start() 형태로 기동.
 */
public class FileAuditWatcher implements Runnable {

    private static final DateTimeFormatter TS =
            DateTimeFormatter.ofPattern("yyyy-MM-dd HH:mm:ss");

    private final Path watchRoot;
    private final Path logDir;
    private final WatchService watchService;
    private final Map<WatchKey, Path> keyMap = new ConcurrentHashMap<>();

    public FileAuditWatcher(Path watchRoot, Path logDir) throws IOException {
        this.watchRoot = watchRoot;
        this.logDir = logDir;
        this.watchService = FileSystems.getDefault().newWatchService();
        Files.createDirectories(logDir);
        registerRecursive(watchRoot);
    }

    /** 하위 디렉토리까지 재귀 등록 */
    private void registerRecursive(Path root) throws IOException {
        Files.walk(root)
             .filter(Files::isDirectory)
             .forEach(dir -> {
                 try {
                     WatchKey key = dir.register(watchService,
                             ENTRY_CREATE, ENTRY_MODIFY, ENTRY_DELETE);
                     keyMap.put(key, dir);
                 } catch (IOException e) {
                     System.err.println("[LHAMS] register failed: " + dir);
                 }
             });
    }

    private String owner(Path file) {
        try {
            PosixFileAttributeView view = Files.getFileAttributeView(
                    file, PosixFileAttributeView.class);
            if (view != null) {
                UserPrincipal p = view.readAttributes().owner();
                return p.getName();
            }
        } catch (IOException ignored) { }
        return "unknown";
    }

    private synchronized void log(String eventType, Path file) {
        String ts = LocalDateTime.now().format(TS);
        String risk = "ENTRY_DELETE".equals(eventType) ? "High" : "Low";
        String line = String.join(" | ",
                ts, mapEvent(eventType), file.toAbsolutePath().toString(),
                owner(file), risk);
        System.out.println("[LHAMS] " + line);

        Path logFile = logDir.resolve("lhams_audit_java_"
                + ts.substring(0, 10) + ".log");   // 일별 파일 로테이션
        try {
            Files.write(logFile, (line + System.lineSeparator()).getBytes(),
                    StandardOpenOption.CREATE, StandardOpenOption.APPEND);
        } catch (IOException e) {
            System.err.println("[LHAMS] log write error: " + e.getMessage());
        }
    }

    private String mapEvent(String kind) {
        Map<String, String> m = new HashMap<>();
        m.put("ENTRY_CREATE", "CREATED");
        m.put("ENTRY_MODIFY", "MODIFIED");
        m.put("ENTRY_DELETE", "DELETED");
        return m.getOrDefault(kind, kind);
    }

    @Override
    public void run() {
        System.out.println("[LHAMS] Java FileAuditWatcher started: " + watchRoot);
        while (!Thread.currentThread().isInterrupted()) {
            WatchKey key;
            try {
                key = watchService.take();
            } catch (InterruptedException e) {
                Thread.currentThread().interrupt();
                break;
            }
            Path dir = keyMap.get(key);
            if (dir == null) { key.reset(); continue; }

            for (WatchEvent<?> event : key.pollEvents()) {
                if (event.kind() == OVERFLOW) continue;
                Path child = dir.resolve((Path) event.context());
                log(event.kind().name(), child);

                // 새 디렉토리 생성 시 감시 대상에 동적 추가
                if (event.kind() == ENTRY_CREATE && Files.isDirectory(child)) {
                    try { registerRecursive(child); }
                    catch (IOException ignored) { }
                }
            }
            if (!key.reset()) keyMap.remove(key);
        }
    }

    public static void main(String[] args) throws Exception {
        Path watch = Paths.get(args.length > 0 ? args[0] : "/mail/test_monitor");
        Path logs  = Paths.get(args.length > 1 ? args[1]
                : "/mail/lhams_project/data/logs");
        new FileAuditWatcher(watch, logs).run();
    }
}
