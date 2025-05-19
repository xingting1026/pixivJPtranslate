import tkinter as tk
from tkinter import scrolledtext, messagebox, ttk
import pixivpy3
import re
from threading import Thread
import queue
from gppt import GetPixivToken
import json
import os
import requests
import time
from datetime import datetime

class PixivNovelReader:
    def __init__(self, root):
        self.root = root
        self.root.title("Pixiv小說閱讀器")
        self.root.geometry("1000x700")
        
        # 設定檔路徑
        self.config_file = "pixiv_config.json"
        
        # 建立介面
        self.setup_ui()
        
        # 初始化Pixiv API
        self.api = None
        self.refresh_token = None
        
        # 用於線程通信的隊列
        self.queue = queue.Queue()
        
        # 載入設定（包括refresh token）
        self.load_config()
        
        # 存儲當前小說資訊
        self.current_novel = None
        
    def setup_ui(self):
        # 頂部框架 - 登入和URL輸入
        top_frame = tk.Frame(self.root)
        top_frame.pack(fill=tk.X, padx=10, pady=5)
        
        # 登入方式選擇
        tk.Label(top_frame, text="登入方式:").grid(row=0, column=0, sticky=tk.W)
        self.login_method = tk.StringVar(value="token")
        
        token_radio = tk.Radiobutton(top_frame, text="使用Token", 
                                    variable=self.login_method, value="token",
                                    command=self.toggle_login_method)
        token_radio.grid(row=0, column=1)
        
        account_radio = tk.Radiobutton(top_frame, text="使用帳密", 
                                      variable=self.login_method, value="account",
                                      command=self.toggle_login_method)
        account_radio.grid(row=0, column=2)
        
        # Token輸入框架
        self.token_frame = tk.Frame(top_frame)
        self.token_frame.grid(row=1, column=0, columnspan=4, pady=5)
        
        tk.Label(self.token_frame, text="Refresh Token:").pack(side=tk.LEFT)
        self.token_entry = tk.Entry(self.token_frame, width=50, show="*")
        self.token_entry.pack(side=tk.LEFT, padx=5)
        
        # 加入保存Token按鈕
        self.save_token_btn = tk.Button(self.token_frame, text="保存Token", 
                                       command=self.save_token)
        self.save_token_btn.pack(side=tk.LEFT, padx=5)
        
        # 帳密輸入框架
        self.account_frame = tk.Frame(top_frame)
        self.account_frame.grid(row=1, column=0, columnspan=4, pady=5)
        self.account_frame.grid_remove()  # 初始隱藏
        
        tk.Label(self.account_frame, text="帳號:").grid(row=0, column=0)
        self.username_entry = tk.Entry(self.account_frame, width=25)
        self.username_entry.grid(row=0, column=1, padx=5)
        
        tk.Label(self.account_frame, text="密碼:").grid(row=0, column=2)
        self.password_entry = tk.Entry(self.account_frame, width=25, show="*")
        self.password_entry.grid(row=0, column=3, padx=5)
        
        # 登入按鈕和狀態
        self.login_btn = tk.Button(top_frame, text="登入", command=self.login)
        self.login_btn.grid(row=2, column=1, pady=5)
        
        self.login_status = tk.Label(top_frame, text="未登入", fg="red")
        self.login_status.grid(row=2, column=2, padx=5)
        
        # URL輸入框架
        url_frame = tk.Frame(self.root)
        url_frame.pack(fill=tk.X, padx=10, pady=5)
        
        tk.Label(url_frame, text="小說URL:").pack(side=tk.LEFT)
        self.url_entry = tk.Entry(url_frame, width=60)
        self.url_entry.pack(side=tk.LEFT, padx=5, expand=True, fill=tk.X)
        
        self.fetch_btn = tk.Button(url_frame, text="獲取小說", command=self.fetch_novel)
        self.fetch_btn.pack(side=tk.LEFT, padx=5)
        self.fetch_btn.config(state=tk.DISABLED)
        
        # 小說資訊框架
        info_frame = tk.Frame(self.root)
        info_frame.pack(fill=tk.X, padx=10, pady=5)
        
        self.title_label = tk.Label(info_frame, text="標題: ", font=("Arial", 12, "bold"))
        self.title_label.pack(anchor=tk.W)
        
        self.author_label = tk.Label(info_frame, text="作者: ")
        self.author_label.pack(anchor=tk.W)
        
        # 增加翻譯按鈕
        translate_frame = tk.Frame(self.root)
        translate_frame.pack(fill=tk.X, padx=10, pady=5)
        
        self.translate_btn = tk.Button(translate_frame, text="翻譯為繁體中文", 
                                       command=self.translate_novel, 
                                       state=tk.DISABLED, 
                                       bg="blue", fg="white")
        self.translate_btn.pack(side=tk.LEFT, padx=5)
        
        # 翻譯進度標籤
        self.translate_status = tk.Label(translate_frame, text="")
        self.translate_status.pack(side=tk.LEFT, padx=10)
        
        # 進度條
        self.progress = ttk.Progressbar(self.root, mode='indeterminate')
        self.progress.pack(fill=tk.X, padx=10, pady=5)
        
        # 文本顯示區域，改為左右兩個
        text_frame = tk.Frame(self.root)
        text_frame.pack(fill=tk.BOTH, expand=True, padx=10, pady=5)
        
        # 原文顯示區域
        left_frame = tk.Frame(text_frame)
        left_frame.pack(side=tk.LEFT, fill=tk.BOTH, expand=True, padx=(0, 5))
        
        tk.Label(left_frame, text="原文", font=("Arial", 10, "bold")).pack()
        self.text_area = scrolledtext.ScrolledText(left_frame, wrap=tk.WORD, width=40, height=25)
        self.text_area.pack(fill=tk.BOTH, expand=True)
        
        # 翻譯顯示區域
        right_frame = tk.Frame(text_frame)
        right_frame.pack(side=tk.RIGHT, fill=tk.BOTH, expand=True, padx=(5, 0))
        
        tk.Label(right_frame, text="翻譯", font=("Arial", 10, "bold")).pack()
        self.translation_area = scrolledtext.ScrolledText(right_frame, wrap=tk.WORD, width=40, height=25)
        self.translation_area.pack(fill=tk.BOTH, expand=True)
        
    def load_config(self):
        """載入設定檔，包括refresh token"""
        if os.path.exists(self.config_file):
            try:
                with open(self.config_file, 'r') as f:
                    config = json.load(f)
                    self.refresh_token = config.get('refresh_token')
                    if self.refresh_token:
                        self.token_entry.insert(0, self.refresh_token)
                        messagebox.showinfo("提示", "已載入保存的Token")
            except Exception as e:
                print(f"載入設定檔失敗: {e}")
    
    def save_config(self):
        """保存設定到檔案"""
        config = {
            'refresh_token': self.refresh_token
        }
        try:
            with open(self.config_file, 'w') as f:
                json.dump(config, f)
        except Exception as e:
            messagebox.showerror("錯誤", f"保存設定失敗: {e}")
    
    def save_token(self):
        """手動保存Token"""
        token = self.token_entry.get()
        if token:
            self.refresh_token = token
            self.save_config()
            messagebox.showinfo("成功", "Token已保存")
        else:
            messagebox.showerror("錯誤", "請輸入Token")
    
    def toggle_login_method(self):
        """切換登入方式的顯示"""
        if self.login_method.get() == "token":
            self.account_frame.grid_remove()
            self.token_frame.grid()
        else:
            self.token_frame.grid_remove()
            self.account_frame.grid()
    
    def login(self):
        """登入Pixiv"""
        if self.login_method.get() == "token":
            self.refresh_token = self.token_entry.get()
            if not self.refresh_token:
                messagebox.showerror("錯誤", "請輸入Refresh Token")
                return
        else:
            username = self.username_entry.get()
            password = self.password_entry.get()
            if not username or not password:
                messagebox.showerror("錯誤", "請輸入帳號和密碼")
                return
            
        self.progress.start()
        Thread(target=self._login_thread, daemon=True).start()
        
    def _login_thread(self):
        """在背景線程中執行登入"""
        try:
            self.api = pixivpy3.AppPixivAPI()
            
            if self.login_method.get() == "token":
                # 使用refresh token登入
                self.api.auth(refresh_token=self.refresh_token)
            else:
                # 使用帳密獲取refresh token
                username = self.username_entry.get()
                password = self.password_entry.get()
                
                g = GetPixivToken(headless=True)
                res = g.login(username=username, password=password)
                self.refresh_token = res["refresh_token"]
                self.api.auth(refresh_token=self.refresh_token)
                
                # 將token保存到介面
                self.root.after(0, lambda: self.token_entry.delete(0, tk.END))
                self.root.after(0, lambda: self.token_entry.insert(0, self.refresh_token))
                
            # 登入成功後自動保存token
            self.save_config()
            self.queue.put(("login_success", None))
        except Exception as e:
            self.queue.put(("login_error", str(e)))
        finally:
            self.check_queue()
            
    def fetch_novel(self):
        """獲取小說內容"""
        url = self.url_entry.get().strip()
        if not url:
            messagebox.showerror("錯誤", "請輸入小說URL")
            return
            
        # 處理兩種URL格式
        # 格式1: https://www.pixiv.net/novel/show.php?id=14804894
        # 格式2: https://www.pixiv.net/novel/14804894
        novel_id = None
        
        # 先嘗試 show.php?id= 格式
        match1 = re.search(r'novel/show\.php\?id=(\d+)', url)
        if match1:
            novel_id = match1.group(1)
            # 將格式1轉換為格式2
            url = f"https://www.pixiv.net/novel/{novel_id}"
        else:
            # 嘗試 novel/數字 格式
            match2 = re.search(r'novel/(\d+)', url)
            if match2:
                novel_id = match2.group(1)
        
        if not novel_id:
            messagebox.showerror("錯誤", "無效的小說URL\n支援格式:\n- https://www.pixiv.net/novel/14804894\n- https://www.pixiv.net/novel/show.php?id=14804894")
            return
        self.progress.start()
        Thread(target=self._fetch_novel_thread, args=(novel_id,), daemon=True).start()
        
    def _fetch_novel_thread(self, novel_id):
        """在背景線程中獲取小說"""
        try:
            # 獲取小說詳情
            novel_detail = self.api.novel_detail(novel_id)
            if 'error' in novel_detail:
                self.queue.put(("fetch_error", novel_detail['error']['message']))
                return
                
            novel = novel_detail['novel']
            title = novel['title']
            author = novel['user']['name']
            
            # 獲取小說正文
            novel_text = self.api.novel_text(novel_id)
            if 'error' in novel_text:
                self.queue.put(("fetch_error", novel_text['error']['message']))
                return
                
            content = novel_text['novel_text']
            
            self.queue.put(("fetch_success", {
                'id': novel_id,
                'title': title,
                'author': author,
                'content': content
            }))
        except Exception as e:
            self.queue.put(("fetch_error", str(e)))
        finally:
            self.check_queue()
    
    def translate_novel(self):
        """翻譯小說"""
        if not self.current_novel:
            messagebox.showerror("錯誤", "請先獲取小說")
            return
            
        # 檢查Ollama是否可用
        if not self.check_ollama_available():
            messagebox.showerror("錯誤", "無法連接到本地Ollama API，請確保Ollama正在運行")
            return
            
        self.translate_btn.config(state=tk.DISABLED)
        self.progress.start()
        Thread(target=self._translate_thread, daemon=True).start()
    
    def check_ollama_available(self):
        """檢查Ollama API是否可用"""
        try:
            response = requests.get("http://localhost:11434/api/tags")
            return response.status_code == 200
        except:
            return False
    
    def _translate_thread(self):
        """在背景線程中進行翻譯"""
        try:
            content = self.current_novel['content']
            # 按換行符分段
            paragraphs = content.split('\n')
            translated_paragraphs = []
            
            total_paragraphs = len(paragraphs)
            
            for i, paragraph in enumerate(paragraphs):
                # 更新進度
                progress_text = f"翻譯進度: {i+1}/{total_paragraphs}"
                self.root.after(0, lambda t=progress_text: self.translate_status.config(text=t))
                
                # 跳過空行
                if not paragraph.strip():
                    translated_paragraphs.append('')
                    continue
                
                # 翻譯段落
                translated = self.translate_with_ollama(paragraph)
                translated_paragraphs.append(translated)
                
                # 即時更新翻譯區域
                current_translation = '\n'.join(translated_paragraphs)
                self.root.after(0, lambda t=current_translation: self.update_translation_display(t))
                
                # 短暫延遲，避免請求過快
                time.sleep(0.1)
            
            # 翻譯完成
            final_translation = '\n'.join(translated_paragraphs)
            self.save_translation(final_translation)
            self.queue.put(("translate_success", final_translation))
            
        except Exception as e:
            self.queue.put(("translate_error", str(e)))
        finally:
            self.check_queue()
    
    def translate_with_ollama(self, text):
        """使用Ollama翻譯文本"""
        url = "http://localhost:11434/api/generate"
        
        # 構建請求
        data = {
            "model": "qwen3:8b",  # 你可以根據需要更改模型名稱
            "prompt": f"請直接翻譯以下內容為繁體中文，按照小說風格語意通順的翻譯，只需要翻譯結果，不要任何解釋或思考過程:\n\n{text}",
            "stream": False
        }
        
        try:
            response = requests.post(url, json=data)
            result = response.json()
            translated = result.get('response', text)
            
            # 過濾掉<think>標籤及其內容
            translated = self.clean_translation(translated)
            
            return translated
        except Exception as e:
            print(f"翻譯錯誤: {e}")
            return text  # 如果翻譯失敗，返回原文
    
    def clean_translation(self, text):
        """清理翻譯結果，移除思考標記和多餘內容"""
        # 移除<think>標籤及其內容
        import re
        cleaned = re.sub(r'<think>.*?</think>', '', text, flags=re.DOTALL)
        
        # 移除可能的指令或提示（如果模型輸出了额外的說明）
        lines = cleaned.split('\n')
        result_lines = []
        
        for line in lines:
            # 過濾掉可能包含指令的行
            if not any(keyword in line.lower() for keyword in ['翻譯', '以下是', '結果', '繁體中文','[新頁]','[newpage]']):
                result_lines.append(line)
        
        # 重新組合並去除多餘的空行
        result = '\n'.join(result_lines)
        result = re.sub(r'\n{3,}', '\n\n', result)  # 將多個連續空行替換為最多兩個
        
        return result.strip()
    
    def update_translation_display(self, text):
        """更新翻譯顯示區域"""
        self.translation_area.delete(1.0, tk.END)
        self.translation_area.insert(1.0, text)
        self.translation_area.see(tk.END)
    
    def save_translation(self, translation):
        """保存翻譯到文件"""
        if not self.current_novel:
            return
            
        # 創建翻譯資料夾
        if not os.path.exists('translations'):
            os.makedirs('translations')
        
        # 生成文件名（使用時間戳和標題）
        timestamp = datetime.now().strftime("%Y%m%d_%H%M%S")
        safe_title = re.sub(r'[<>:"/\\|?*]', '_', self.current_novel['title'])
        filename = f"translations/{timestamp}_{safe_title}_translation.txt"
        
        try:
            with open(filename, 'w', encoding='utf-8') as f:
                f.write(f"標題: {self.current_novel['title']}\n")
                f.write(f"作者: {self.current_novel['author']}\n")
                f.write(f"小說ID: {self.current_novel['id']}\n")
                f.write(f"翻譯時間: {datetime.now().strftime('%Y-%m-%d %H:%M:%S')}\n")
                f.write("-" * 40 + "\n\n")
                f.write(translation)
            
            # 同時保存原文
            original_filename = f"translations/{timestamp}_{safe_title}_original.txt"
            with open(original_filename, 'w', encoding='utf-8') as f:
                f.write(f"標題: {self.current_novel['title']}\n")
                f.write(f"作者: {self.current_novel['author']}\n")
                f.write(f"小說ID: {self.current_novel['id']}\n")
                f.write("-" * 40 + "\n\n")
                f.write(self.current_novel['content'])
                
        except Exception as e:
            print(f"保存翻譯失敗: {e}")
    
    def check_queue(self):
        """檢查隊列中的消息"""
        try:
            while True:
                msg_type, data = self.queue.get_nowait()
                
                if msg_type == "login_success":
                    self.progress.stop()
                    self.login_status.config(text="已登入", fg="green")
                    self.fetch_btn.config(state=tk.NORMAL)
                    messagebox.showinfo("成功", "登入成功！")
                    
                elif msg_type == "login_error":
                    self.progress.stop()
                    messagebox.showerror("錯誤", f"登入失敗: {data}")
                    
                elif msg_type == "fetch_success":
                    self.progress.stop()
                    self.current_novel = data
                    self.title_label.config(text=f"標題: {data['title']}")
                    self.author_label.config(text=f"作者: {data['author']}")
                    
                    # 顯示小說內容
                    self.text_area.delete(1.0, tk.END)
                    self.text_area.insert(1.0, data['content'])
                    self.text_area.see(1.0)
                    
                    # 啟用翻譯按鈕
                    self.translate_btn.config(state=tk.NORMAL)
                    
                elif msg_type == "fetch_error":
                    self.progress.stop()
                    messagebox.showerror("錯誤", f"獲取小說失敗: {data}")
                    
                elif msg_type == "translate_success":
                    self.progress.stop()
                    self.translate_btn.config(state=tk.NORMAL)
                    self.translate_status.config(text="翻譯完成！")
                    self.translation_area.delete(1.0, tk.END)
                    self.translation_area.insert(1.0, data)
                    messagebox.showinfo("成功", "翻譯完成並已保存到文件")
                    
                elif msg_type == "translate_error":
                    self.progress.stop()
                    self.translate_btn.config(state=tk.NORMAL)
                    self.translate_status.config(text="翻譯失敗")
                    messagebox.showerror("錯誤", f"翻譯失敗: {data}")
                    
        except queue.Empty:
            pass
        finally:
            self.root.after(100, self.check_queue)

def main():
    root = tk.Tk()
    app = PixivNovelReader(root)
    root.mainloop()

if __name__ == "__main__":
    main()