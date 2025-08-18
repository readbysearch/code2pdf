#!/bin/bash
# File with special characters in content

echo "Testing special chars: $@, \$HOME, \`date\`"
echo 'Single quotes: $HOME won'"'"'t expand'
echo "Backslashes: \\ \n \t"

# Unicode characters
echo "Unicode: 你好 世界 🌍"