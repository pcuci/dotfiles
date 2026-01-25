# GitLab CI Local completions
###-begin-gitlab-ci-local-completions-###
_gitlab-ci-local_yargs_completions() {
    local cur_word args type_list
    cur_word="${COMP_WORDS[COMP_CWORD]}"
    args=("${COMP_WORDS[@]}")
    type_list=$(gitlab-ci-local --get-yargs-completions "${args[@]}")
    COMPREPLY=( $(compgen -W "${type_list}" -- "${cur_word}") )
    if [ ${#COMPREPLY[@]} -eq 0 ]; then
      COMPREPLY=()
    fi
    return 0
}
complete -o bashdefault -o default -F _gitlab-ci-local_yargs_completions gitlab-ci-local
###-end-gitlab-ci-local-completions-###

# Set GOPATH
export GOPATH=$HOME/go

# Set WIN_IP from resolv.conf
export WIN_IP=$(awk '/nameserver / {print $2; exit}' /etc/resolv.conf)

# Add custom paths to PATH
paths_to_add=(
  "$HOME/.local/bin"
  "$HOME/.pulumi/bin"
  "${KREW_ROOT:-$HOME/.krew}/bin"
  "$HOME/.linkerd2/bin"
  "$GOPATH/bin"
  "$HOME/.cargo/bin"
  "/snap/bin"
  "$HOME/.dotfiles/bin"
)
for path in "${paths_to_add[@]}"; do
  if [[ ":$PATH:" != *":$path:"* ]]; then
    export PATH="$PATH:$path"
  fi
done

# Configure no_proxy for Kubernetes
if [[ ":$no_proxy:" != *":kubernetes.docker.internal:"* ]]; then
  export no_proxy="$no_proxy,kubernetes.docker.internal"
fi

# Disable update prompts
export DISABLE_UPDATE_PROMPT=true

# Set DISPLAY for WSL X11
# --- WSL-only DISPLAY setup (safe with/without WSLg) ---
is_wsl() {
  # True if running under WSL1/WSL2
  grep -qiE 'microsoft|wsl' /proc/sys/kernel/osrelease 2>/dev/null
}

if is_wsl; then
  # Don’t override when using ssh -X/-Y inside WSL
  if [ -z "$SSH_CONNECTION" ]; then
    # If WSLg is present, DISPLAY/WAYLAND are already set correctly
    if [ -d /mnt/wslg ] || [ -n "$WAYLAND_DISPLAY" ]; then
      : # do nothing – WSLg handles DISPLAY/Wayland
    else
      # Legacy X server on Windows (VcXsrv/X410/etc.)
      host_ip="$(awk '/^nameserver /{print $2; exit}' /etc/resolv.conf 2>/dev/null)"
      if [ -n "$host_ip" ] && { [ -z "$DISPLAY" ] || echo "$DISPLAY" | grep -qE '^(|127\.)'; }; then
        export DISPLAY="${host_ip}:0"
        # Optional: helps some OpenGL-on-WSL1 setups
        export LIBGL_ALWAYS_INDIRECT=1
      fi
    fi
  fi
fi
# --- end WSL-only block ---


# Source FZF
source ~/.fzf.bash

# Initialize NVM (Node Version Manager)
export NVM_DIR="$HOME/.nvm"
[ -s "$NVM_DIR/nvm.sh" ] && . "$NVM_DIR/nvm.sh" # This loads nvm

# Define proxy commands
proxy_on() {
    export HTTP_PROXY=http://proxy.ubisoft.org:3128
    export HTTPS_PROXY=$HTTP_PROXY
    export NO_PROXY=".ubisoft.com,.ubisoft.org,10.0.0.0/8,172.16.0.0/12,172.17.0.1,192.168.0.0/16,localhost,127.0.0.1,dev.hydra.local,*.hydra-dev"
    export http_proxy=$HTTP_PROXY
    export https_proxy=$HTTP_PROXY
    export no_proxy=$NO_PROXY
    echo "Proxy enabled."
}

proxy_off() {
    unset HTTP_PROXY HTTPS_PROXY NO_PROXY http_proxy https_proxy no_proxy
    echo "Proxy disabled."
}

# Export private GitLab settings
export GOPRIVATE=gitlab-ncsa.ubisoft.org

# Set GPG_TTY
export GPG_TTY=$(tty)

# Source user-defined aliases
source ~/.bash_aliases

# Initialize Starship prompt
eval "$(starship init bash)"

export PYTHONUTF8=1
[ -s "$NVM_DIR/bash_completion" ] && \. "$NVM_DIR/bash_completion"  # This loads nvm bash_completion
eval "$(/home/linuxbrew/.linuxbrew/bin/brew shellenv)"
