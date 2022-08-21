#!/bin/bash
curl -o- https://raw.githubusercontent.com/nvm-sh/nvm/v0.34.0/install.sh | bash
source /.nvm/nvm.sh
nvm install --lts
npm config set prefix "/home/ec2-user/node_modules"
cd /home/ec2-user/
npm install express --save
iptables -t nat -A PREROUTING -i eth0 -p tcp --dport 80 -j REDIRECT --to-port 8080
cat <<'EOF' >> app.js
let express = require('express');
let app = express();

app.get('/api', (req, res) => {
  console.log(JSON.stringify(req.headers));
  let message = {
    timestamp: new Date().toISOString(),
    headers: req.headers,
  };
  res.json(message);
});

app.listen(8080, () => {
  console.log('api is up!');
});
EOF
node app.js > stdout.txt 2> stderr.txt &