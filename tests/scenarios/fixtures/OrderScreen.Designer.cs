namespace Example
{
    public partial class OrderScreen
    {
        private void InitializeComponent()
        {
            this.gvwOrders = new DevExpress.XtraGrid.Views.Grid.GridView();
            this.btnOpen = new DevExpress.XtraEditors.SimpleButton();
            this.btnOpen.Visible = false;
            this.btnOpen.Font = new System.Drawing.Font("맑은 고딕", 10F);
            this.btnOpen.Click += new System.EventHandler(this.btnOpen_Click);
        }

        private DevExpress.XtraGrid.Views.Grid.GridView gvwOrders;
        private DevExpress.XtraEditors.SimpleButton btnOpen;
    }
}
