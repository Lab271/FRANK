#!/bin/sh
set -e
VSCODE_USER_PROFILE=${VSCODE_USER_PROFILE:-"Default"} # set your VSCode user profile  if needed
INSTALLED_EXTENSIONS=$(code --list-extensions --show-versions --profile "$VSCODE_USER_PROFILE")
VSCODE_VULN_EXTENSIONS=(
  JuanFBlanco.awswhh
  ETHFoundry.etherfoundrys
  EllisonBrett.givingblankies
  MarcusLockwood.wgbk
  VitalikButerin-EthFoundation.blan-co
  ShowSnowcrypto.SnowShoNo
  Crypto-Extensions.SnowShsoNo
  Rojo.rojo-roblox-vscode
  cline-ai-main.cline-ai-agent@3.1.3 
)
OPENVSX_VULN_EXTENSIONS=(
  codejoy.codejoy-vscode-extension@1.8.3  
  codejoy.codejoy-vscode-extension@1.8.4  
  l-igh-t.vscode-theme-seti-folder@1.2.3  
  kleinesfilmroellchen.serenity-dsl-syntaxhighlight@0.3.2  
  JScearcy.rust-doc-viewer@4.2.1  
  SIRILMP.dark-theme-sm@3.11.4  
  CodeInKlingon.git-worktree-menu@1.0.9  
  CodeInKlingon.git-worktree-menu@1.0.91  
  ginfuru.better-nunjucks@0.3.2  
  ellacrity.recoil@0.7.4  
  grrrck.positron-plus-1-e@0.0.71  
  jeronimoekerdt.color-picker-universal@2.8.91  
  srcery-colors.srcery-colors@0.3.9  
  ChainDevTools.solidity-pro
  kilocode-ai.kilo-code
  nomic-fdn.hardhat-solidity
  oxc-vscode.oxc
  juan-blanco.solidity
  kineticsquid.solidity-ethereum-vsc
  ETHFoundry.solidityethereum
  JuanFBlanco.solidity-ai-ethereum
  Ethereum.solidity-ethereum
  juan-blanco.solidity
  NomicFdn.hardhat-solidity
  juan-blanco.vscode-solidity
  nomic-foundation.hardhat-solidity
  nomic-fdn.solidity-hardhat
  Crypto-Extensions.solidity
  Crypto-Extensions.SnowShsoNo
)
echo "Checking for vulnerable extensions..."
for EXT in "${VSCODE_VULN_EXTENSIONS[@]}"; do
  if echo "$INSTALLED_EXTENSIONS" | grep -q "^$EXT$"; then
    echo "🔴 Vulnerable extension found: $EXT"
  else
    echo "🟢 Extension ok: $EXT"
  fi
done
for EXT in "${OPENVSX_VULN_EXTENSIONS[@]}"; do
  if echo "$INSTALLED_EXTENSIONS" | grep -q "^$EXT$"; then
    echo "🔴 Vulnerable extension found: $EXT"
  else
    echo "🟢 Extension ok: $EXT"
  fi
done
echo "Check complete."