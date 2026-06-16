# 1) Dashboard sync – 09:00, 13:00, 17:00, 21:00 every day
0 9,13,17,21 * * * /home/admin/dashboard_sync.sh >> /home/admin/dashboard_sync.log 2>&1

# 2) Git auto update – keep as-is (09:00 every Saturday)
59 10 * * 6 /home/admin/chat_app/git_auto_update.sh >> /home/admin/chat_app/cron.log 2>&1

# 3) Backend sync – 09:00, 13:00, 17:00, 21:00 every day
0 9,13,17,21 * * * /home/admin/backend_sync.sh >> /home/admin/backend_sync.log 2>&1

# 4) Frontend sync – 09:00, 13:00, 17:00, 21:00 every day
0 9,13,17,21 * * * /home/admin/frontend_sync.sh >> /home/admin/frontend_sync.log 2>&1

# 5) WPE frontend+backend sync - 09:00 everyday
#0 9 * * * flock -n /tmp/auto-deploy.lock /home/admin/auto-deploy.sh >> /home/admin/cron.log 2>&1