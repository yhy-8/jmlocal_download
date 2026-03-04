import customtkinter as ctk
import tkinter.messagebox as messagebox
import threading
import jmcomic
import os
import shutil
import re
import textwrap

# 设置全局外观：跟随系统深色/浅色模式，主题色为蓝色
ctk.set_appearance_mode("System")
ctk.set_default_color_theme("blue")


class ComicDownloaderApp(ctk.CTk):
    def __init__(self):
        super().__init__()

        self.title("JMComic 漫画下载器 (CBZ打包版)")
        self.geometry("800x600")
        self.minsize(500, 350)
        self.resizable(True, True)

        self.font_title = ("Microsoft YaHei", 24, "bold")
        self.font_main = ("Microsoft YaHei", 16)
        self.font_status = ("Microsoft YaHei", 12)

        self.option = None
        self.setup_ui()
        self.load_option()

    def load_option(self):
        # 定义目标文件夹和配置文件路径
        target_dir = './jm漫画'
        config_path = os.path.join(target_dir, 'option.yml')

        try:
            # 1. 确保 ./jm漫画 文件夹存在，不存在就自动创建
            os.makedirs(target_dir, exist_ok=True)

            # 2. 检查配置文件是否存在，如果不存在则释放默认配置
            if not os.path.exists(config_path):
                print("未找到配置文件，正在生成默认配置...")
                builtin_yaml = textwrap.dedent("""
                                client:
                                  cache: null
                                  domain: []
                                  impl: api
                                  postman:
                                    meta_data:
                                      headers: null
                                      impersonate: chrome110
                                      proxies: {}
                                    type: curl_cffi
                                  retry_times: 5
                                dir_rule:
                                  base_dir: ./temp_jm
                                  rule: Bd_Pindextitle
                                download:
                                  cache: true
                                  image:
                                    decode: true
                                    suffix: null
                                  threading:
                                    image: 30
                                    photo: 16
                                log: true
                                plugins:
                                  valid: log
                                version: '2.1'
                                """).strip()
                # 将默认配置写入到 ./jm漫画/option.yml，并且保留文件不删除
                with open(config_path, 'w', encoding='utf-8') as f:
                    f.write(builtin_yaml.strip())
                self.status_var.set("就绪 (已生成并加载默认 option.yml)")
            else:
                self.status_var.set("就绪 (已加载已有的 option.yml)")

            # 3. 使用绝对稳妥的方法，从文件加载配置
            self.option = jmcomic.create_option_by_file(config_path)

        except Exception as e:
            # 如果加载失败（比如用户自己把 yaml 格式改错乱了）
            error_msg = str(e)
            self.after(500,
                       lambda msg=error_msg: messagebox.showerror("初始化错误",
                                                                  f"配置加载失败\n错误详情: {msg}\n请尝试删除 ./jm漫画/option.yml 重新打开软件"))
            self.entry.configure(state="disabled")
            self.btn.configure(state="disabled")
            self.status_var.set("状态：配置加载失败")

    def setup_ui(self):
        self.center_frame = ctk.CTkFrame(self, fg_color="transparent")
        self.center_frame.pack(fill="both", expand=True)

        self.title_label = ctk.CTkLabel(self.center_frame, text="请输入漫画 Album ID", font=self.font_title)
        self.title_label.pack(pady=(60, 20))

        self.id_var = ctk.StringVar()
        self.entry = ctk.CTkEntry(self.center_frame, textvariable=self.id_var, font=self.font_main,
                                  width=350, height=45, justify="center", placeholder_text="例如: 1237704")
        self.entry.pack(pady=(0, 20))
        self.entry.focus()

        self.entry.bind("<Return>", lambda event: self.on_download_click())

        self.btn = ctk.CTkButton(self.center_frame, text="开始下载", font=self.font_main,
                                 width=200, height=45, command=self.on_download_click)
        self.btn.pack(pady=(0, 20))

        self.status_var = ctk.StringVar(value="就绪...")
        self.status_label = ctk.CTkLabel(self, textvariable=self.status_var,
                                         font=self.font_status, text_color="gray")
        self.status_label.pack(side="bottom", fill="x", pady=(0, 10))

    def on_download_click(self):
        if self.option is None:
            messagebox.showwarning("警告", "配置未加载，请确保 option.yml 存在。")
            return

        album_id_str = self.id_var.get().strip()
        if not album_id_str.isdigit():
            messagebox.showwarning("输入错误", "请输入有效的纯数字 ID！")
            return

        album_id = int(album_id_str)

        self.btn.configure(state="disabled", text="处理中...")
        self.entry.configure(state="disabled")
        self.status_var.set("正在获取漫画信息...")

        threading.Thread(target=self.download_task, args=(album_id,), daemon=True).start()

    def download_task(self, album_id):
        try:
            # 1. 获取相册信息（提取漫画名）
            client = self.option.build_jm_client()
            album = client.get_album_detail(album_id)

            # 清理漫画名中不能用于文件命名的特殊字符
            safe_title = re.sub(r'[\\/*?:"<>|]', "", album.title).strip()
            if not safe_title:
                safe_title = str(album_id)

            self.after(0, lambda msg=safe_title: self.status_var.set(f"正在下载: {msg} ..."))

            # 2. 执行下载
            jmcomic.download_album(album_id, self.option)

            # 3. 获取 jmcomic 实际保存该相册的目录路径
            try:
                album_dir = self.option.dir_rule.decide_album_root_dir(album)
            except AttributeError:
                base_dir = getattr(self.option.dir_rule, 'base_dir', './')
                album_dir = os.path.join(base_dir, album.title)

            # 4. 执行打包和重命名逻辑
            if os.path.exists(album_dir):
                self.after(0, lambda msg=safe_title: self.status_var.set(f"下载完成，正在打包 CBZ: {msg}..."))

                # 【修改点开始】指定目标文件夹为同级的 ./jm漫画
                target_dir = "./jm漫画"
                os.makedirs(target_dir, exist_ok=True) # 如果文件夹不存在，则自动创建

                # 设定压缩包的基础路径（放入 target_dir 里面）
                archive_base_path = os.path.join(target_dir, safe_title)
                # 【修改点结束】

                # 打包成 zip
                shutil.make_archive(archive_base_path, 'zip', album_dir)

                # 重命名为 cbz
                zip_path = f"{archive_base_path}.zip"
                cbz_path = f"{archive_base_path}.cbz"

                if os.path.exists(cbz_path):
                    os.remove(cbz_path)
                os.rename(zip_path, cbz_path)

                # 打包完成后，删除原文件夹释放空间
                shutil.rmtree(album_dir)
            else:
                raise Exception(f"下载似乎成功了，但我找不到存放图片的文件夹，无法打包。\n推测路径为: {album_dir}")

            self.after(0, self.on_download_success)

        except Exception as e:
            error_msg = str(e)
            self.after(0, lambda msg=error_msg: self.on_download_failed(msg))

    def on_download_success(self):
        self.btn.configure(state="normal", text="开始下载")
        self.entry.configure(state="normal")
        self.status_var.set("下载并打包完成！")
        self.id_var.set("")
        messagebox.showinfo("成功", "漫画下载并已打包为 CBZ 格式！")

    def on_download_failed(self, error_msg):
        self.btn.configure(state="normal", text="开始下载")
        self.entry.configure(state="normal")
        self.status_var.set("下载或打包失败！")
        messagebox.showerror("错误", f"处理异常：\n{error_msg}")


if __name__ == "__main__":
    app = ComicDownloaderApp()
    app.mainloop()