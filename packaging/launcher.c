/*
 * BG Matte 런처 — .app 번들의 실행 파일(Contents/MacOS/BGMatte)이 됩니다.
 *
 * 하는 일
 *   1. Contents/Resources/launch.conf 에서 (1행) 파이썬 경로, (2행) 프로젝트 폴더를 읽는다.
 *   2. 프로젝트 폴더로 이동해 `python -m bgmatte_app` 을 '자식 프로세스'로 실행한다.
 *   3. 자식의 출력은 로그 파일로 보내고, 자식이 끝나면 같은 종료 코드로 끝난다.
 *
 * 왜 exec가 아니라 자식 프로세스인가
 *   macOS의 카메라 권한은 '책임 프로세스'(responsible process)에 붙는다. 이 런처를 책임
 *   프로세스로 남겨 두면 Info.plist의 NSCameraUsageDescription이 적용되어 권한 팝업에
 *   "BG Matte"로 표시된다. 런처가 exec로 파이썬으로 바뀌어 버리면 권한 대상이 파이썬
 *   바이너리가 되어 팝업이 뜨지 않거나 앱이 강제 종료될 수 있다.
 *
 * 빌드: clang -O2 -Wall -o BGMatte launcher.c   (packaging/build_app.sh 가 수행)
 */

#define _GNU_SOURCE
#include <errno.h>
#include <fcntl.h>
#include <limits.h>
#include <signal.h>
#include <spawn.h>
#include <stdint.h>
#include <stdio.h>
#include <stdlib.h>
#include <string.h>
#include <sys/stat.h>
#include <sys/types.h>
#include <sys/wait.h>
#include <unistd.h>

#ifdef __APPLE__
#include <mach-o/dyld.h>
#endif

extern char **environ;

static volatile sig_atomic_t g_child = 0;
static volatile sig_atomic_t g_forwarded = 0;

static void forward_signal(int sig) {
    g_forwarded = 1;
    if (g_child > 0) kill((pid_t)g_child, sig);
}

static int self_path(char *buf, size_t size) {
#ifdef __APPLE__
    uint32_t n = (uint32_t)size;
    char raw[PATH_MAX];
    if (_NSGetExecutablePath(raw, &n) != 0) return -1;
    if (!realpath(raw, buf)) return -1;
    return 0;
#else
    ssize_t n = readlink("/proc/self/exe", buf, size - 1);
    if (n < 0) return -1;
    buf[n] = '\0';
    return 0;
#endif
}

/* 사용자에게 보이는 오류 창. 따옴표/역슬래시는 셸 인젝션을 막기 위해 공백으로 바꾼다. */
static void alert(const char *message) {
    fprintf(stderr, "[BG Matte] %s\n", message);
#ifdef __APPLE__
    char safe[1024];
    size_t j = 0;
    for (size_t i = 0; message[i] && j + 1 < sizeof safe; i++) {
        char c = message[i];
        safe[j++] = (c == '"' || c == '\'' || c == '\\' || c == '\n' || c == '\r') ? ' ' : c;
    }
    safe[j] = '\0';
    char cmd[2048];
    snprintf(cmd, sizeof cmd,
             "/usr/bin/osascript -e 'display alert \"BG Matte\" message \"%s\" as critical' >/dev/null 2>&1",
             safe);
    (void)system(cmd);
#endif
}

static void mkdir_p(const char *path) {
    char tmp[PATH_MAX];
    snprintf(tmp, sizeof tmp, "%s", path);
    for (char *p = tmp + 1; *p; p++) {
        if (*p == '/') {
            *p = '\0';
            mkdir(tmp, 0755);
            *p = '/';
        }
    }
    mkdir(tmp, 0755);
}

static void chomp(char *s) {
    size_t n = strlen(s);
    while (n > 0 && (s[n - 1] == '\n' || s[n - 1] == '\r')) s[--n] = '\0';
}

int main(void) {
    char exe[PATH_MAX];
    if (self_path(exe, sizeof exe) != 0) {
        alert("실행 파일의 위치를 확인하지 못했습니다.");
        return 2;
    }

    /* <app>/Contents/MacOS/BGMatte → <app>/Contents */
    char *slash = strrchr(exe, '/');
    if (slash) *slash = '\0';
    slash = strrchr(exe, '/');
    if (slash) *slash = '\0';

    char conf_path[PATH_MAX + 32];
    snprintf(conf_path, sizeof conf_path, "%s/Resources/launch.conf", exe);
    FILE *f = fopen(conf_path, "r");
    if (!f) {
        alert("launch.conf를 읽을 수 없습니다. packaging/build_app.sh 를 다시 실행해 주세요.");
        return 2;
    }
    char python[PATH_MAX] = "", root[PATH_MAX] = "";
    if (!fgets(python, sizeof python, f) || !fgets(root, sizeof root, f)) {
        fclose(f);
        alert("launch.conf 형식이 올바르지 않습니다. packaging/build_app.sh 를 다시 실행해 주세요.");
        return 2;
    }
    fclose(f);
    chomp(python);
    chomp(root);

    if (access(python, X_OK) != 0) {
        char msg[PATH_MAX + 200];
        snprintf(msg, sizeof msg,
                 "Python을 찾을 수 없습니다: %s  conda 환경(bgmatte)을 활성화한 상태에서 "
                 "packaging/build_app.sh 를 다시 실행해 주세요.",
                 python);
        alert(msg);
        return 2;
    }
    if (chdir(root) != 0) {
        char msg[PATH_MAX + 200];
        snprintf(msg, sizeof msg,
                 "프로젝트 폴더를 찾을 수 없습니다: %s  폴더를 옮겼다면 build_app.sh 를 다시 실행해 주세요.", root);
        alert(msg);
        return 2;
    }

    /* 로그 파일 (앱 본체 설정의 log_path()와 같은 위치) */
    const char *home = getenv("HOME");
    char logdir[PATH_MAX], logfile[PATH_MAX + 16];
#ifdef __APPLE__
    snprintf(logdir, sizeof logdir, "%s/Library/Logs/BGMatte", home ? home : "/tmp");
#else
    snprintf(logdir, sizeof logdir, "%s/.cache/BGMatte", home ? home : "/tmp");
#endif
    mkdir_p(logdir);
    snprintf(logfile, sizeof logfile, "%s/app.log", logdir);

    /* PYTHONPATH 앞에 프로젝트 폴더를 붙여 `-m bgmatte_app` 과 utils.py 를 찾게 한다. */
    const char *old_path = getenv("PYTHONPATH");
    char new_path[PATH_MAX * 2 + 2];
    if (old_path && *old_path)
        snprintf(new_path, sizeof new_path, "%s:%s", root, old_path);
    else
        snprintf(new_path, sizeof new_path, "%s", root);
    setenv("PYTHONPATH", new_path, 1);
    setenv("PYTHONUNBUFFERED", "1", 1);

    posix_spawn_file_actions_t actions;
    posix_spawn_file_actions_init(&actions);
    posix_spawn_file_actions_addopen(&actions, 0, "/dev/null", O_RDONLY, 0);
    posix_spawn_file_actions_addopen(&actions, 1, logfile, O_WRONLY | O_CREAT | O_APPEND, 0644);
    posix_spawn_file_actions_adddup2(&actions, 1, 2);

    char *args[] = {python, (char *)"-m", (char *)"bgmatte_app", NULL};

    struct sigaction sa;
    memset(&sa, 0, sizeof sa);
    sa.sa_handler = forward_signal;
    sigemptyset(&sa.sa_mask);
    sigaction(SIGTERM, &sa, NULL);
    sigaction(SIGINT, &sa, NULL);
    sigaction(SIGHUP, &sa, NULL);

    pid_t pid = 0;
    int rc = posix_spawn(&pid, python, &actions, NULL, args, environ);
    posix_spawn_file_actions_destroy(&actions);
    if (rc != 0) {
        char msg[PATH_MAX + 200];
        snprintf(msg, sizeof msg, "Python을 실행하지 못했습니다 (%s): %s", strerror(rc), python);
        alert(msg);
        return 2;
    }
    g_child = (sig_atomic_t)pid;

    int status = 0;
    while (waitpid(pid, &status, 0) < 0) {
        if (errno != EINTR) {
            alert("앱 프로세스를 기다리는 중 오류가 발생했습니다.");
            return 2;
        }
    }

    int code = 0;
    if (WIFEXITED(status))
        code = WEXITSTATUS(status);
    else if (WIFSIGNALED(status))
        code = 128 + WTERMSIG(status);

    /* 사용자가 직접 종료한 경우가 아니라면 이유를 알려준다. */
    if (code != 0 && !g_forwarded) {
        char msg[PATH_MAX + 200];
        snprintf(msg, sizeof msg, "BG Matte가 예기치 않게 종료되었습니다 (코드 %d).  로그: %s", code, logfile);
        alert(msg);
    }
    return code;
}
