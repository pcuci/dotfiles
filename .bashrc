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
export DISPLAY=$(awk '/nameserver / {print $2; exit}' /etc/resolv.conf 2>/dev/null):0

# Initialize keychain for SSH keys: one-time keychain init with lock + notice
if [[ -z "$SSH_AUTH_SOCK" ]]; then
  lock="$HOME/.cache/keychain.lock"
  mkdir -p "$(dirname "$lock")"
  exec 9>"$lock"

  if flock -n 9; then
    # First shell: start agent and export vars
    eval "$(keychain --quiet --eval --agents ssh --inherit any --quick id_ed25519)"
  else
    echo "[$$] Waiting for keychain lock: $lock"
    for i in {1..20}; do
      f="$HOME/.keychain/$(hostname -s)-sh"
      if [[ -f "$f" ]]; then
        # bring vars into *this* shell
        # shellcheck disable=SC1090
        . "$f"
        break
      fi
      sleep 0.25
    done
    echo "[$$] Lock released, continuing…"
  fi
fi

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
